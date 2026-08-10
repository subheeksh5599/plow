"""Plow — the write path for agent-executed yield.

Policy-gated deposits through KeeperHub's execution layer:
scan positions -> rank venues (live APY, degrade-safe) -> gate -> execute (sponsored)
-> verify onchain. Exposed as MCP-shaped JSON-RPC tools + a CLI.
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
import os
import time
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------- config
KH_BASE = os.environ.get("KEEPERHUB_BASE", "https://app.keeperhub.com")
CHAIN = os.environ.get("KEEPERHUB_CHAIN", "sepolia")
CHAIN_ID = int(os.environ.get("KEEPERHUB_CHAIN_ID", "11155111"))
RPC = os.environ.get(
    "KEEPERHUB_RPC_OVERRIDE",
    "https://ethereum-sepolia-rpc.publicnode.com",
)
BLOCKSCOUT = os.environ.get(
    "PLOW_BLOCKSCOUT",
    "https://eth-sepolia.blockscout.com/api",
)
POLICY_PATH = os.environ.get("PLOW_POLICY_PATH", os.path.join(os.path.dirname(__file__), "policies.json"))
AUDIT_DIR = os.environ.get("PLOW_AUDIT_DIR", os.path.join(os.path.dirname(__file__), "..", "audits"))
FAIL_CLOSED = os.environ.get("PLOW_FAIL_CLOSED", "1") == "1"

_request_key: contextvars.ContextVar[str] = contextvars.ContextVar("plow_request_key", default="")


def active_key() -> str:
    return _request_key.get().strip() or os.environ.get("KH_API_KEY", "").strip()


# ---------------------------------------------------------------- ABIs
# Standard ERC-20 (approve/balanceOf/transfer/allowance) — the asset side.
ABI_ERC20 = json.dumps(
    [
        {"type": "function", "name": "approve", "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}], "stateMutability": "nonpayable"},
        {"type": "function", "name": "balanceOf", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
        {"type": "function", "name": "transfer", "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}], "stateMutability": "nonpayable"},
        {"type": "function", "name": "allowance", "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    ]
)

# Aave V3 Pool (supply/withdraw) — the real venue surface.
ABI_AAVE_POOL = json.dumps(
    [
        {"type": "function", "name": "supply", "inputs": [{"name": "asset", "type": "address"}, {"name": "amount", "type": "uint256"}, {"name": "onBehalfOf", "type": "address"}, {"name": "referralCode", "type": "uint16"}], "outputs": [], "stateMutability": "nonpayable"},
        {"type": "function", "name": "withdraw", "inputs": [{"name": "asset", "type": "address"}, {"name": "amount", "type": "uint256"}, {"name": "to", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "nonpayable"},
        {"type": "function", "name": "getReserveData", "inputs": [{"name": "asset", "type": "address"}], "outputs": [{"name": "", "type": "tuple"}], "stateMutability": "view"},
    ]
)


# ---------------------------------------------------------------- policy
def load_policy() -> dict:
    with open(POLICY_PATH) as f:
        return json.load(f)


def _utc_hour() -> int:
    return int(time.strftime("%H", time.gmtime()))


def gate_deposit(policy: dict, venue_id: str, amount: float, simulate: Optional[dict], simulate_required: bool = True) -> dict:
    """Policy gate: ALLOW / DENY / ESCALATE with a full check list.

    simulate_required=False runs the pre-gate (allowlist/cap/budget/window) BEFORE
    any transaction is spent — the simulation check is deferred, never DENYing.
    """
    checks: list[dict] = []
    venues = {v["id"]: v for v in policy["venues"]}
    venue = venues.get(venue_id)

    def check(name: str, ok: bool, detail: str):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    if not venue:
        check("allowlist", False, f"venue {venue_id} not in allowlist")
        return {"decision": "DENY", "reason": f"venue {venue_id} not allowlisted", "checks": checks}

    if not venue.get("enabled", True):
        check("allowlist", False, f"venue {venue_id} disabled")
        return {"decision": "DENY", "reason": f"venue {venue_id} disabled", "checks": checks}

    if not venue.get("address") or venue["address"].lower() == "0x" + "0" * 40:
        check("executable", False, f"venue {venue_id} has no executable address")
        return {"decision": "DENY", "reason": f"venue {venue_id} has no executable address", "checks": checks}

    check("allowlist", True, f"venue {venue_id} allowlisted")

    if amount <= 0:
        check("amount_cap", False, "amount must be > 0")
        return {"decision": "DENY", "reason": "amount must be > 0", "checks": checks}

    cap = float(venue.get("maxDeposit", 0))
    check("amount_cap", amount <= cap, f"{amount} <= cap {cap}")

    # per-period budget from audit trail
    period_h = int(venue.get("budgetPeriodHours", 24))
    budget = float(venue.get("budget", 0))
    spent = audit_spent(venue_id, period_h)
    check("budget", spent + amount <= budget, f"spent {spent:.2f} + {amount:.2f} <= budget {budget:.2f}")

    # active window (UTC hours) — supports wraparound ranges like 23→5
    win = policy.get("window", {"start": 0, "end": 23})
    hour = _utc_hour()
    w_start, w_end = int(win["start"]), int(win["end"])
    in_window = (w_start <= hour <= w_end) if w_start <= w_end else (hour >= w_start or hour <= w_end)
    check("window", in_window, f"utc {hour} in window {win}")

    # function allowlist — the venue declares the function it executes
    fn = venue.get("functionName", "deposit").lower()
    fns = [f.lower() for f in policy.get("functionAllowlist", [])]
    allowed = any(fn in f for f in fns)
    check("function_allowlist", allowed, f"{fn} allowed: {fns}")

    # simulation gate — fail closed
    if simulate is None:
        if not simulate_required:
            check("simulation", True, "deferred to post-approval (pre-gate)")
        else:
            check("simulation", not FAIL_CLOSED, "simulation unavailable")
            if FAIL_CLOSED:
                return {"decision": "DENY", "reason": "simulation unavailable (fail closed)", "checks": checks}
    elif simulate.get("wouldRevert") is not False:
        check("simulation", False, f"simulate wouldRevert={simulate.get('wouldRevert')}")
        return {"decision": "DENY", "reason": "simulation reverted (fail closed)", "checks": checks}
    else:
        check("simulation", True, f"gasEstimate={simulate.get('gasEstimate')}")

    over_budget = spent + amount > budget

    failed = [c["check"] for c in checks if not c["ok"]]
    if failed:
        # ESCALATE only when budget is the single failing check; everything
        # else (allowlist, cap, window, simulation) is a hard DENY.
        if set(failed) == {"budget"} and over_budget:
            return {"decision": "ESCALATE", "reason": "over per-period budget", "checks": checks}
        return {"decision": "DENY", "reason": f"failed checks: {failed}", "checks": checks}

    return {"decision": "ALLOW", "reason": "in policy", "checks": checks}


# ---------------------------------------------------------------- audit
def _audit_path() -> str:
    os.makedirs(AUDIT_DIR, exist_ok=True)
    return os.path.join(AUDIT_DIR, "plow-audit.jsonl")


def audit_append(record: dict):
    record.setdefault("ts", int(time.time()))
    with open(_audit_path(), "a") as f:
        f.write(json.dumps(record) + "\n")


def audit_spent(venue_id: str, period_hours: int) -> float:
    now = time.time()
    cutoff = now - period_hours * 3600
    total = 0.0
    try:
        with open(_audit_path()) as f:
            for line in f:
                r = json.loads(line)
                if r.get("venue_id") == venue_id and r.get("ts", 0) >= cutoff and r.get("decision") == "ALLOW":
                    total += float(r.get("amount", 0))
    except FileNotFoundError:
        pass
    return total


def stable_intent_key(venue_id: str, amount: float, chain: str) -> str:
    h = hashlib.sha256(f"plow:{venue_id}:{amount:.6f}:{chain}".encode()).hexdigest()
    return h[:24]


def load_audit() -> list:
    """Read the audit trail back (empty list if missing)."""
    path = _audit_path()
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def list_escalations() -> dict:
    """Pending ESCALATE decisions awaiting a human (human-in-the-loop)."""
    pending = [r for r in load_audit() if r.get("decision") == "ESCALATE" and not r.get("resolved")]
    return {
        "escalations": [
            {
                "index": i,
                "venue_id": r.get("venue_id"),
                "amount": r.get("amount"),
                "chain": r.get("chain"),
                "reason": r.get("reason"),
                "intent_key": r.get("intent_key"),
            }
            for i, r in enumerate(pending)
        ],
        "count": len(pending),
    }


async def resolve_escalation(index: int, approve: bool) -> dict:
    """Resolve a pending escalation. approve=True re-runs the gated deposit."""
    records = load_audit()
    pending_idx = [i for i, r in enumerate(records) if r.get("decision") == "ESCALATE" and not r.get("resolved")]
    if index >= len(pending_idx):
        return {"ok": False, "error": f"no pending escalation at index {index}"}
    pos = pending_idx[index]
    rec = records[pos]
    rec["resolved"] = True
    rec["resolved_ts"] = int(time.time())
    rec["resolution"] = "APPROVED" if approve else "REJECTED"
    with open(_audit_path(), "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    audit_append({"event": "escalation_resolved", "index": index, "decision": rec["resolution"], "venue_id": rec.get("venue_id"), "amount": rec.get("amount"), "intent_key": rec.get("intent_key")})
    if not approve:
        return {"ok": True, "decision": "REJECTED", "reason": "rejected by operator"}
    return await execute_deposit(rec["venue_id"], rec["amount"], auto_approve_escalation=True)


# ---------------------------------------------------------------- KeeperHub client
async def kh_request(method: str, path: str, body: Optional[dict] = None, timeout: float = 60.0) -> dict:
    key = active_key()
    if not key:
        raise RuntimeError("kh_api_key_not_set")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(base_url=KH_BASE, timeout=timeout) as client:
        resp = await client.request(method, path, headers=headers, json=body)
    if resp.status_code >= 400:
        try:
            err = resp.json()
        except Exception:
            err = {"error": "http_error", "detail": resp.text[:300]}
        raise RuntimeError(json.dumps({"status": resp.status_code, **err}))
    return resp.json()


async def kh_contract_call(
    address: str,
    fn: str,
    args: list,
    abi: str,
    simulate: bool = False,
) -> dict:
    body = {
        "contractAddress": address,
        "chainId": CHAIN_ID,
        "functionName": fn,
        "functionArgs": json.dumps(args),
        "abi": abi,
    }
    if simulate:
        body["simulate"] = True
    key = active_key()
    if not key:
        raise RuntimeError("kh_api_key_not_set")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(base_url=KH_BASE, timeout=60) as client:
        resp = None
        for attempt in range(3):
            resp = await client.post("/api/execute/contract-call", headers=headers, json=body)
            if resp.status_code < 500 or attempt == 2:
                break
            await asyncio.sleep(2.5 * (attempt + 1))
    if resp.status_code >= 400:
        try:
            err = resp.json()
        except Exception:
            err = {"error": "http_error", "detail": resp.text[:300]}
        # a reverting simulation returns 4xx with a structured simulate result
        if simulate and isinstance(err, dict) and err.get("wouldRevert") is not None:
            return err
        raise RuntimeError(json.dumps({"status": resp.status_code, **err}))
    return resp.json()


async def kh_execution_status(execution_id: str) -> dict:
    return await kh_request("GET", f"/api/execute/{execution_id}/status")


async def kh_execution_status_poll(execution_id: str, attempts: int = 4, delay: float = 1.5,
                                   status_fn=None) -> dict:
    """Poll an execution's status until a transactionHash appears (B8).

    Direct-execution status can lag the write; a single read may return no
    hash yet. Terminal failure states stop early. `status_fn` is injectable
    for tests — defaults to the live KeeperHub status read.
    """
    fn = status_fn or kh_execution_status
    last: dict = {}
    for i in range(attempts):
        last = await fn(execution_id)
        if last.get("transactionHash"):
            return last
        state = str(last.get("status", "")).lower()
        if state in ("failed", "error", "reverted", "cancelled", "canceled"):
            return last
        if i < attempts - 1:
            await asyncio.sleep(delay)
    return last


async def kh_wallet_address() -> str:
    data = await kh_request("GET", "/api/integrations")
    for integ in data if isinstance(data, list) else data.get("integrations", data.get("data", [])):
        if isinstance(integ, dict) and integ.get("type") == "web3":
            return integ.get("address") or integ.get("walletAddress") or integ.get("data", {}).get("address", "")
    raise RuntimeError("no web3 wallet integration found")


# ---------------------------------------------------------------- RPC reads
BALANCE_OF_SELECTOR = "0x70a08231"
ALLOWANCE_SELECTOR = "0xdd62ed3e"


def _erc20_balance_calldata(token: str, who: str) -> str:
    who = who.lower().replace("0x", "").rjust(64, "0")
    return f"{BALANCE_OF_SELECTOR}{who}"


def _erc20_allowance_calldata(token: str, owner: str, spender: str) -> str:
    owner = owner.lower().replace("0x", "").rjust(64, "0")
    spender = spender.lower().replace("0x", "").rjust(64, "0")
    return f"{ALLOWANCE_SELECTOR}{owner}{spender}"


async def _rpc_call(data: str, to: str) -> int:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to.lower(), "data": data}, "latest"],
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(RPC, json=payload)
        result = resp.json().get("result")
    return int(result or "0x0", 16)


async def rpc_read_erc20(token: str, who: str) -> int:
    return await _rpc_call(_erc20_balance_calldata(token, who), token)


async def rpc_read_erc20_allowance(token: str, owner: str, spender: str) -> int:
    return await _rpc_call(_erc20_allowance_calldata(token, owner, spender), token)


async def rpc_native_balance(who: str) -> int:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance", "params": [who.lower(), "latest"]}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(RPC, json=payload)
        result = resp.json().get("result")
    return int(result or "0x0", 16)


# ---------------------------------------------------------------- scan + rank
_yields_cache: dict = {"ts": 0, "data": []}


async def defillama_yields(force: bool = False) -> list:
    now = time.time()
    if not force and _yields_cache["ts"] and now - _yields_cache["ts"] < 900:
        return _yields_cache["data"]
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://yields.llama.fi/pools")
        resp.raise_for_status()
        _yields_cache["data"] = resp.json().get("data", [])
        _yields_cache["ts"] = now
    return _yields_cache["data"]


async def scan_positions(address: str, token_configs: Optional[list] = None) -> dict:
    """Read stablecoin balances for an address across configured tokens."""
    policy = load_policy()
    tokens = policy.get("tokens", []) if token_configs is None else token_configs
    positions = []
    for t in tokens:
        try:
            raw = await rpc_read_erc20(t["address"], address)
        except Exception:
            continue
        amount = raw / (10 ** int(t.get("decimals", 6)))
        if amount > 0:
            positions.append({"symbol": t["symbol"], "address": t["address"], "decimals": t.get("decimals", 6), "amount": round(amount, 6), "source": "eth_call balanceOf"})
    positions.sort(key=lambda p: p["amount"], reverse=True)
    return {"address": address, "chain": CHAIN, "positions": positions, "sources": [f"eth_call balanceOf on {CHAIN}"]}


async def rank_venues(positions: Optional[list] = None) -> dict:
    """Rank allowlisted venues by LIVE DefiLlama APY.

    No fallback: if the yield feed is unreachable the call fails loudly, and a
    venue whose pool cannot be matched is excluded (never ranked on made-up
    rates).
    """
    policy = load_policy()
    pools = await defillama_yields()
    ranked = []
    for v in policy["venues"]:
        if not v.get("enabled", True):
            continue
        want_proj = v.get("defillamaProject", "").lower()
        want_sym = v.get("defillamaSymbol", "").upper()
        best = None
        for pool in pools:
            if str(pool.get("project", "")).lower() != want_proj:
                continue
            if str(pool.get("symbol", "")).upper() != want_sym:
                continue
            # prefer Ethereum pools over L2 lookalikes
            rank_chain = 0 if str(pool.get("chain", "")) == "Ethereum" else 1
            if best is None or rank_chain < best[0]:
                apy_raw = float(pool.get("apy") or pool.get("apyBase") or 0)
                best = (rank_chain, pool, apy_raw)
        if not best:
            continue  # no live pool — do not rank on fabricated rates
        _, pool, apy_raw = best
        tvl = pool.get("tvlUsd", 0)
        ranked.append({
            "venue_id": v["id"],
            "name": v.get("name", v["id"]),
            "address": v.get("address"),
            "apy": round(apy_raw, 2),
            "apySource": f"defillama {pool.get('project')}/{pool.get('symbol')} tvl=${tvl:,.0f}",
            "addressable": bool(v.get("address")) and v["address"].lower() != "0x" + "0" * 40,
            "maxDeposit": v.get("maxDeposit", 0),
        })
    ranked.sort(key=lambda r: r["apy"], reverse=True)
    return {"chain": CHAIN, "ranked": ranked, "poolCount": len(pools)}


# ---------------------------------------------------------------- execution
def _token_decimals(policy: dict, token_address: str) -> int:
    for t in policy.get("tokens", []):
        if str(t.get("address", "")).lower() == token_address.lower():
            return int(t.get("decimals", 18))
    return 18


async def _simulate_supply(venue: dict, amount: int, on_behalf: str) -> dict:
    return await kh_contract_call(
        venue["address"],
        "supply",
        [venue["tokenAddress"], amount, on_behalf, 0],
        ABI_AAVE_POOL,
        simulate=True,
    )


async def execute_deposit(
    venue_id: str,
    amount: float,
    address: Optional[str] = None,
    approve: bool = True,
    auto_approve_escalation: bool = False,
) -> dict:
    """Full gated supply: scan balance -> exact-approve (if needed) -> simulate ->
    gate -> supply (Aave V3) -> verify aToken balance."""
    policy = load_policy()
    venues = {v["id"]: v for v in policy["venues"]}
    venue = venues.get(venue_id)
    if not venue:
        return {"ok": False, "error": f"venue {venue_id} not in allowlist"}

    if not address:
        address = await kh_wallet_address()

    token = venue.get("tokenAddress")
    if not token:
        return {"ok": False, "error": "venue missing tokenAddress"}
    decimals = _token_decimals(policy, token)
    amount_units = int(round(amount * 10**decimals))

    txs: list = []
    approve_hash: Optional[str] = None
    intent_key = stable_intent_key(venue_id, amount, CHAIN)

    # 0) PRE-GATE — zero-transaction checks before any spend (allowlist, cap,
    #    budget, window). DENY/ESCALATE here means nothing has been broadcast.
    pre = gate_deposit(policy, venue_id, amount, None, simulate_required=False)
    if pre["decision"] == "DENY":
        audit_append({"venue_id": venue_id, "amount": amount, "chain": CHAIN, "decision": "DENY", "reason": pre["reason"], "checks": pre["checks"], "intent_key": intent_key})
        return {"ok": False, "decision": "DENY", "reason": pre["reason"], "checks": pre["checks"], "txs": 0}
    if pre["decision"] == "ESCALATE" and not auto_approve_escalation:
        audit_append({"venue_id": venue_id, "amount": amount, "chain": CHAIN, "decision": "ESCALATE", "reason": pre["reason"], "checks": pre["checks"], "intent_key": intent_key})
        return {"ok": False, "decision": "ESCALATE", "reason": pre["reason"], "checks": pre["checks"], "txs": 0}

    # 1) exact approval (PREFILL-07: never max-uint), only if allowance is short
    try:
        current_allowance = await rpc_read_erc20_allowance(token, address, venue["address"])
    except Exception:
        return {"ok": False, "decision": "DENY", "reason": "allowance read failed (fail closed)", "txs": 0}

    if current_allowance < amount_units:
        sim_approve = await kh_contract_call(token, "approve", [venue["address"], amount_units], ABI_ERC20, simulate=True)
        if sim_approve.get("wouldRevert") is not False:
            return {"ok": False, "decision": "DENY", "reason": "approve simulation reverted", "txs": 0}
        if approve:
            exec_approve = await kh_contract_call(token, "approve", [venue["address"], amount_units], ABI_ERC20)
            approve_id = exec_approve.get("executionId")
            if approve_id:
                approve_status = await kh_execution_status_poll(approve_id)
                approve_hash = approve_status.get("transactionHash")
                txs.append(approve_id)

    # 2) simulate the supply (now that approval is in place)
    simulate = await _simulate_supply(venue, amount_units, address)

    # 3) gate
    verdict = gate_deposit(policy, venue_id, amount, simulate)

    record = {
        "venue_id": venue_id,
        "amount": amount,
        "chain": CHAIN,
        "decision": verdict["decision"],
        "reason": verdict["reason"],
        "checks": verdict["checks"],
        "simulate": {k: simulate.get(k) for k in ("status", "gasEstimate", "wouldRevert")},
        "intent_key": intent_key,
    }
    audit_append(record)

    if verdict["decision"] == "DENY":
        return {"ok": False, "decision": "DENY", "reason": verdict["reason"], "checks": verdict["checks"], "txs": len(txs)}

    if verdict["decision"] == "ESCALATE" and not auto_approve_escalation:
        return {"ok": False, "decision": "ESCALATE", "reason": verdict["reason"], "checks": verdict["checks"], "txs": len(txs)}

    # 4) supply (write executes; sponsored on testnets)
    exec_dep = await kh_contract_call(venue["address"], "supply", [token, amount_units, address, 0], ABI_AAVE_POOL)
    dep_id = exec_dep.get("executionId")
    txs.append(dep_id)
    dep_status = await kh_execution_status_poll(dep_id) if dep_id else {}
    tx_hash = dep_status.get("transactionHash")
    sponsored = dep_status.get("sponsored")

    # 5) verify onchain (aToken balance)
    verified = await verify_position(address, venue_id)

    record.update({
        "approve_tx": approve_hash,
        "deposit_execution": dep_id,
        "transaction_hash": tx_hash,
        "transaction_link": dep_status.get("transactionLink"),
        "sponsored": sponsored,
        "verified": verified.get("ok"),
        "shares_after": verified.get("shares"),
    })
    audit_append(record)

    return {
        "ok": True,
        "decision": "ALLOW",
        "reason": verdict["reason"],
        "checks": verdict["checks"],
        "execution_id": dep_id,
        "transaction_hash": tx_hash,
        "transaction_link": dep_status.get("transactionLink"),
        "sponsored": sponsored,
        "verified": verified,
        "txs": len(txs),
    }


async def execute_withdraw(
    venue_id: str,
    amount: float,
    address: Optional[str] = None,
    auto_approve_escalation: bool = False,
) -> dict:
    """Policy-gated Aave withdraw: simulate -> gate -> withdraw -> verify balance."""
    policy = load_policy()
    venues = {v["id"]: v for v in policy["venues"]}
    venue = venues.get(venue_id)
    if not venue:
        return {"ok": False, "error": f"venue {venue_id} not in allowlist"}
    if not address:
        address = await kh_wallet_address()

    token = venue.get("tokenAddress")
    decimals = _token_decimals(policy, token or "")
    amount_units = int(round(amount * 10**decimals))
    intent_key = stable_intent_key(f"{venue_id}:withdraw", amount, CHAIN)

    pre = gate_deposit(policy, venue_id, amount, None, simulate_required=False)
    if pre["decision"] == "DENY":
        return {"ok": False, "decision": "DENY", "reason": pre["reason"], "checks": pre["checks"], "txs": 0}
    if pre["decision"] == "ESCALATE" and not auto_approve_escalation:
        return {"ok": False, "decision": "ESCALATE", "reason": pre["reason"], "checks": pre["checks"], "txs": 0}

    simulate = await kh_contract_call(venue["address"], "withdraw", [token, amount_units, address], ABI_AAVE_POOL, simulate=True)
    verdict = gate_deposit(policy, venue_id, amount, simulate)
    audit_append({"venue_id": venue_id, "amount": amount, "chain": CHAIN, "action": "withdraw", "decision": verdict["decision"], "reason": verdict["reason"], "checks": verdict["checks"], "intent_key": intent_key})
    if verdict["decision"] != "ALLOW":
        return {"ok": False, "decision": verdict["decision"], "reason": verdict["reason"], "checks": verdict["checks"], "txs": 0}

    exec_w = await kh_contract_call(venue["address"], "withdraw", [token, amount_units, address], ABI_AAVE_POOL)
    w_id = exec_w.get("executionId")
    w_status = await kh_execution_status_poll(w_id) if w_id else {}
    return {
        "ok": True,
        "decision": "ALLOW",
        "execution_id": w_id,
        "transaction_hash": w_status.get("transactionHash"),
        "transaction_link": w_status.get("transactionLink"),
        "sponsored": w_status.get("sponsored"),
        "txs": 1,
    }


async def verify_position(address: str, venue_id: str) -> dict:
    policy = load_policy()
    venues = {v["id"]: v for v in policy["venues"]}
    venue = venues.get(venue_id)
    if not venue:
        return {"ok": False, "error": f"venue {venue_id} not found"}
    # Aave venues expose an aToken; anything else verifies on the venue itself
    target = venue.get("aTokenAddress") or venue["address"]
    try:
        shares = await rpc_read_erc20(target, address)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": shares > 0, "venue_id": venue_id, "shares": shares, "shares_formatted": round(shares / 1e18, 6), "source": f"eth_call balanceOf onchain ({target[:10]}…)"}


# ---------------------------------------------------------------- MCP tools
TOOLS = [
    {
        "name": "scan_positions",
        "description": "Read stablecoin balances for an address on the configured chain.",
        "parameters": {"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"]},
    },
    {
        "name": "rank_venues",
        "description": "Rank allowlisted yield venues by LIVE DefiLlama APY (no fallback: feed failure fails loudly, unmatched venues are excluded).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "execute_deposit",
        "description": "Policy-gated Aave supply: simulate, gate, exact-approve, supply via KeeperHub (sponsored), verify aToken.",
        "parameters": {
            "type": "object",
            "properties": {
                "venue_id": {"type": "string"},
                "amount": {"type": "number"},
                "address": {"type": "string"},
                "auto_approve_escalation": {"type": "boolean"},
            },
            "required": ["venue_id", "amount"],
        },
    },
    {
        "name": "execute_withdraw",
        "description": "Policy-gated Aave withdraw: simulate, gate, withdraw via KeeperHub (sponsored).",
        "parameters": {
            "type": "object",
            "properties": {
                "venue_id": {"type": "string"},
                "amount": {"type": "number"},
                "address": {"type": "string"},
            },
            "required": ["venue_id", "amount"],
        },
    },
    {
        "name": "verify_position",
        "description": "Read the onchain share balance for an address in a venue.",
        "parameters": {"type": "object", "properties": {"address": {"type": "string"}, "venue_id": {"type": "string"}}, "required": ["address", "venue_id"]},
    },
    {
        "name": "list_escalations",
        "description": "List ESCALATE decisions awaiting a human (human-in-the-loop).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "resolve_escalation",
        "description": "Approve or reject a pending escalation; approve re-runs the gated deposit.",
        "parameters": {
            "type": "object",
            "properties": {"index": {"type": "integer"}, "approve": {"type": "boolean"}},
            "required": ["index", "approve"],
        },
    },
]


async def mcp_call(name: str, args: dict) -> dict:
    if name == "scan_positions":
        return await scan_positions(args["address"])
    if name == "rank_venues":
        return await rank_venues()
    if name == "execute_deposit":
        return await execute_deposit(
            args["venue_id"],
            float(args["amount"]),
            address=args.get("address"),
            auto_approve_escalation=bool(args.get("auto_approve_escalation", False)),
        )
    if name == "execute_withdraw":
        return await execute_withdraw(args["venue_id"], float(args["amount"]), address=args.get("address"))
    if name == "verify_position":
        return await verify_position(args["address"], args["venue_id"])
    if name == "list_escalations":
        return list_escalations()
    if name == "resolve_escalation":
        return await resolve_escalation(int(args["index"]), bool(args["approve"]))
    raise RuntimeError(f"unknown tool {name}")


# ---------------------------------------------------------------- ASGI app
async def app(scope, receive, send):
    if scope["type"] != "http":
        return

    headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
    _request_key.set(headers.get("authorization", "").replace("Bearer ", "").strip() or headers.get("x-api-key", "").strip())

    path = scope.get("path", "")
    method = scope.get("method", "GET")
    origin = headers.get("origin", "")

    if method == "OPTIONS":
        await _respond(send, 204, {}, headers=origin)
        return

    if path == "/api/health" and method == "GET":
        await _respond(send, 200, {"ok": True, "service": "plow", "chain": CHAIN})
        return

    if path == "/api/plow" and method == "POST":
        body = await _read_body(receive)
        try:
            req = json.loads(body)
        except Exception:
            await _respond(send, 400, {"error": "invalid_json"})
            return
        try:
            if req.get("method") == "tools/list":
                result = {"tools": TOOLS}
            elif req.get("method") == "tools/call":
                params = req.get("params", {})
                result = await mcp_call(params.get("name", ""), params.get("arguments", {}))
            else:
                result = {"error": "unknown_method"}
            await _respond(send, 200, {"jsonrpc": "2.0", "id": req.get("id"), "result": result})
        except Exception as e:
            await _respond(send, 200, {"jsonrpc": "2.0", "id": req.get("id"), "error": {"message": str(e), "type": type(e).__name__}})
        return

    await _respond(send, 404, {"error": "not_found"}, headers=origin)


async def _read_body(receive):
    chunks = []
    while True:
        msg = await receive()
        chunks.append(msg.get("body", b""))
        if not msg.get("more_body"):
            break
    return b"".join(chunks)


async def _respond(send, status: int, payload: dict, headers: str = ""):
    body = json.dumps(payload).encode()
    hdrs = [
        [b"content-type", b"application/json"],
        [b"content-length", str(len(body)).encode()],
    ]
    if headers:
        hdrs.append([b"access-control-allow-origin", headers.encode()])
        hdrs.append([b"access-control-allow-headers", b"authorization, x-api-key, content-type"])
        hdrs.append([b"access-control-allow-methods", b"GET, POST, OPTIONS"])
    await send({"type": "http.response.start", "status": status, "headers": hdrs})
    await send({"type": "http.response.body", "body": body})


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)
