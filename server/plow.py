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
MOCK_USDC = os.environ.get("PLOW_MOCK_USDC", "0x032b4f813F0E21bAD8B6Bd497a8a6841B8a28dd9")
ABI_MOCK_USDC = json.dumps(
    [
        {"type": "function", "name": "approve", "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}], "stateMutability": "nonpayable"},
        {"type": "function", "name": "balanceOf", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
        {"type": "function", "name": "mint", "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [], "stateMutability": "nonpayable"},
        {"type": "function", "name": "transfer", "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}], "stateMutability": "nonpayable"},
        {"type": "function", "name": "transferFrom", "inputs": [{"name": "from_", "type": "address"}, {"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}], "stateMutability": "nonpayable"},
        {"type": "function", "name": "allowance", "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    ]
)

ABI_MOCK_SKY = json.dumps(
    [
        {"type": "function", "name": "deposit", "inputs": [{"name": "amount", "type": "uint256"}], "outputs": [{"type": "uint256"}], "stateMutability": "nonpayable"},
        {"type": "function", "name": "withdraw", "inputs": [{"name": "shares", "type": "uint256"}], "outputs": [{"type": "uint256"}], "stateMutability": "nonpayable"},
        {"type": "function", "name": "balanceOf", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
        {"type": "function", "name": "rateBps", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
        {"type": "function", "name": "underlying", "inputs": [], "outputs": [{"type": "address"}], "stateMutability": "view"},
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

    # function allowlist
    fns = [f.lower() for f in policy.get("functionAllowlist", [])]
    check("function_allowlist", "deposit" in " ".join(fns), f"deposit allowed: {fns}")

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
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.get("https://yields.llama.fi/pools")
            _yields_cache["data"] = resp.json().get("data", [])
            _yields_cache["ts"] = now
    except Exception:
        return _yields_cache["data"]  # degrade: keep last known, or []
    return _yields_cache["data"]


async def scan_positions(address: str, token_configs: Optional[list] = None) -> dict:
    """Read stablecoin balances for an address across configured tokens."""
    policy = load_policy()
    tokens = token_configs or policy.get("tokens", [])
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
    """Rank allowlisted venues by live APY; degrade to configured APY on failure."""
    policy = load_policy()
    pools = await defillama_yields()
    ranked = []
    degraded = False
    for v in policy["venues"]:
        if not v.get("enabled", True):
            continue
        apy = None
        source = None
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
        if best:
            _, pool, apy_raw = best
            tvl = pool.get("tvlUsd", 0)
            apy = round(apy_raw, 2)
            source = f"defillama {pool.get('project')}/{pool.get('symbol')} tvl=${tvl:,.0f}"
        if apy is None or apy <= 0:
            apy = float(v.get("apyOverride", 0))
            source = "config override (degrade path)"
            degraded = True
        ranked.append({
            "venue_id": v["id"],
            "name": v.get("name", v["id"]),
            "address": v.get("address"),
            "apy": apy,
            "apySource": source,
            "addressable": bool(v.get("address")) and v["address"].lower() != "0x" + "0" * 40,
            "maxDeposit": v.get("maxDeposit", 0),
        })
    ranked.sort(key=lambda r: r["apy"], reverse=True)
    return {"chain": CHAIN, "ranked": ranked, "degraded": degraded, "poolCount": len(pools)}


# ---------------------------------------------------------------- execution
async def _simulate_deposit(venue: dict, amount: int) -> dict:
    return await kh_contract_call(venue["address"], "deposit", [amount], ABI_MOCK_SKY, simulate=True)


async def execute_deposit(
    venue_id: str,
    amount: float,
    address: Optional[str] = None,
    approve: bool = True,
    auto_approve_escalation: bool = False,
) -> dict:
    """Full gated deposit: scan balance -> exact-approve (if needed) -> simulate ->
    gate -> deposit -> verify."""
    policy = load_policy()
    venues = {v["id"]: v for v in policy["venues"]}
    venue = venues.get(venue_id)
    if not venue:
        return {"ok": False, "error": f"venue {venue_id} not in allowlist"}

    if not address:
        address = await kh_wallet_address()

    amount_units = int(round(amount * 1e6))  # USDC 6 decimals
    token = venue.get("tokenAddress")
    if not token:
        return {"ok": False, "error": "venue missing tokenAddress"}

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
        sim_approve = await kh_contract_call(token, "approve", [venue["address"], amount_units], ABI_MOCK_USDC, simulate=True)
        if sim_approve.get("wouldRevert") is not False:
            return {"ok": False, "decision": "DENY", "reason": "approve simulation reverted", "txs": 0}
        if approve:
            exec_approve = await kh_contract_call(token, "approve", [venue["address"], amount_units], ABI_MOCK_USDC)
            approve_id = exec_approve.get("executionId")
            if approve_id:
                approve_status = await kh_execution_status(approve_id)
                approve_hash = approve_status.get("transactionHash")
                txs.append(approve_id)

    # 2) simulate the deposit (now that approval is in place)
    simulate = await _simulate_deposit(venue, amount_units)

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

    # 3) deposit (write executes; sponsored on testnets)
    exec_dep = await kh_contract_call(venue["address"], "deposit", [amount_units], ABI_MOCK_SKY)
    dep_id = exec_dep.get("executionId")
    txs.append(dep_id)
    dep_status = await kh_execution_status(dep_id)
    tx_hash = dep_status.get("transactionHash")
    sponsored = dep_status.get("sponsored")

    # 4) verify onchain
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


async def verify_position(address: str, venue_id: str) -> dict:
    policy = load_policy()
    venues = {v["id"]: v for v in policy["venues"]}
    venue = venues.get(venue_id)
    if not venue:
        return {"ok": False, "error": f"venue {venue_id} not found"}
    try:
        shares = await rpc_read_erc20(venue["address"], address)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": shares > 0, "venue_id": venue_id, "shares": shares, "shares_formatted": round(shares / 1e18, 6), "source": "eth_call balanceOf onchain"}


# ---------------------------------------------------------------- MCP tools
TOOLS = [
    {
        "name": "scan_positions",
        "description": "Read stablecoin balances for an address on the configured chain.",
        "parameters": {"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"]},
    },
    {
        "name": "rank_venues",
        "description": "Rank allowlisted yield venues by live APY (degrades to config on lookup failure).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "execute_deposit",
        "description": "Policy-gated deposit: simulate, gate, exact-approve, deposit via KeeperHub (sponsored), verify.",
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
