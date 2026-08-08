"""Plow unit tests — plain asserts, no framework. Run: python server/test_plow.py"""
import asyncio
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("KH_API_KEY", "kh_test_key")
os.environ["PLOW_FAIL_CLOSED"] = "1"

import plow  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  {status} {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def test_stable_intent_key_deterministic():
    a = plow.stable_intent_key("mock-sky", 1000.0, "sepolia")
    b = plow.stable_intent_key("mock-sky", 1000.0, "sepolia")
    c = plow.stable_intent_key("mock-sky", 1000.01, "sepolia")
    check("intent key deterministic", a == b)
    check("intent key changes with amount", a != c)
    check("intent key length", len(a) == 24)


def test_gate_deny_unlisted():
    policy = plow.load_policy()
    v = plow.gate_deposit(policy, "ghost-venue", 100.0, {"wouldRevert": False})
    check("unlisted venue denied", v["decision"] == "DENY", str(v))
    check("deny reason names allowlist", "allowlist" in v["reason"], v["reason"])


def test_gate_deny_disabled_venue():
    policy = plow.load_policy()
    v = plow.gate_deposit(policy, "unlisted-venue", 100.0, {"wouldRevert": False})
    check("disabled venue denied", v["decision"] == "DENY", str(v))


def test_gate_deny_unaddressed_venue():
    policy = plow.load_policy()
    v = plow.gate_deposit(policy, "mock-spark", 100.0, {"wouldRevert": False})
    check("rank-only venue denied", v["decision"] == "DENY", str(v))
    check("deny reason executable", "executable" in v["reason"], v["reason"])


def test_gate_deny_zero_amount():
    policy = plow.load_policy()
    v = plow.gate_deposit(policy, "mock-sky", 0, {"wouldRevert": False})
    check("zero amount denied", v["decision"] == "DENY")


def test_gate_deny_cap_exceeded():
    policy = plow.load_policy()
    v = plow.gate_deposit(policy, "mock-sky", 99999.0, {"wouldRevert": False})
    check("cap exceeded denied", v["decision"] == "DENY", v["reason"])


def test_gate_deny_simulate_reverted():
    policy = plow.load_policy()
    v = plow.gate_deposit(policy, "mock-sky", 100.0, {"wouldRevert": True})
    check("reverting simulate denied", v["decision"] == "DENY")


def test_gate_deny_simulate_unavailable_fail_closed():
    policy = plow.load_policy()
    v = plow.gate_deposit(policy, "mock-sky", 100.0, None)
    check("missing simulation fails closed", v["decision"] == "DENY")


def test_gate_allow_in_policy():
    policy = plow.load_policy()
    v = plow.gate_deposit(policy, "mock-sky", 100.0, {"wouldRevert": False, "gasEstimate": 80000})
    check("in-policy deposit allowed", v["decision"] == "ALLOW", str(v))
    check("all checks ok", all(c["ok"] for c in v["checks"]))


def test_gate_escalate_over_budget():
    # force spent > budget by writing audit records into a temp audit dir
    tmp = tempfile.mkdtemp()
    old_dir = plow.AUDIT_DIR
    plow.AUDIT_DIR = tmp
    try:
        for _ in range(60):
            plow.audit_append({"venue_id": "mock-sky", "amount": 200.0, "decision": "ALLOW", "ts": int(__import__("time").time())})
        policy = plow.load_policy()
        v = plow.gate_deposit(policy, "mock-sky", 100.0, {"wouldRevert": False})
        check("over budget escalates", v["decision"] == "ESCALATE", v["reason"])
    finally:
        plow.AUDIT_DIR = old_dir


def test_byok_precedence():
    os.environ["KH_API_KEY"] = "kh_test_key"
    plow._request_key.set("kh_per_request")
    check("per-request key wins", plow.active_key() == "kh_per_request")
    plow._request_key.set("")
    check("env fallback", plow.active_key() == "kh_test_key")


def test_abi_selector_deposit():
    calldata = plow._erc20_balance_calldata("0x9fE46701507954886cD7bA1E5a8a9f9eF4a2a9e71a2", "0x1776D4D751d97c85845bF54e6CE364CEc62D4bBf")
    check("balanceOf selector", calldata.startswith(plow.BALANCE_OF_SELECTOR))
    check("calldata length", len(calldata) == 2 + 8 + 64)


def test_rank_degrades_when_no_pools():
    async def run():
        plow._yields_cache["ts"] = time.time()  # honor the cache — no live fetch
        plow._yields_cache["data"] = []
        r = await plow.rank_venues()
        return r

    r = asyncio.run(run())
    check("rank returns venues", len(r["ranked"]) >= 2, str(r))
    check("rank degraded flag (no pools)", r["degraded"] is True)
    check("rank sorted desc", r["ranked"][0]["apy"] >= r["ranked"][-1]["apy"])
    check("rank degrade source", "degrade" in r["ranked"][0]["apySource"])


def test_rank_live_when_pools_match():
    # fixture: real DefiLlama-shaped pools for the configured hints
    fixture = [
        {"project": "sky-lending", "symbol": "SUSDS", "chain": "Ethereum", "apy": 3.52, "apyBase": 3.52, "tvlUsd": 1_000_000_000},
        {"project": "ethena-usde", "symbol": "SUSDE", "chain": "Ethereum", "apy": 4.03, "apyBase": 4.03, "tvlUsd": 2_000_000_000},
        {"project": "aave-v3", "symbol": "USDC", "chain": "Ethereum", "apy": 3.46, "apyBase": 3.46, "tvlUsd": 500_000_000},
    ]

    async def run():
        plow._yields_cache["ts"] = time.time()
        plow._yields_cache["data"] = fixture
        r = await plow.rank_venues()
        return r

    r = asyncio.run(run())
    check("rank NOT degraded with live pools", r["degraded"] is False, str(r))
    for entry in r["ranked"]:
        check(f"live source for {entry['venue_id']}", "defillama" in entry["apySource"], entry["apySource"])
        check(f"positive apy {entry['venue_id']}", entry["apy"] > 0)
    check("rank order", r["ranked"][0]["apy"] == 4.03, str(r["ranked"][0]))


def test_scan_zero_positions_no_crash():
    async def run():
        plow._yields_cache["data"] = []
        return await plow.scan_positions("0x0000000000000000000000000000000000000000", token_configs=[])

    r = asyncio.run(run())
    check("scan empty returns structure", r["positions"] == [] and r["chain"] == "sepolia")


def test_escalation_lifecycle():
    """list_escalations finds an ESCALATE record; reject resolves it."""
    import tempfile

    tmp = tempfile.mkdtemp()
    plow.AUDIT_DIR = tmp  # module constant is bound at import — patch it directly
    plow.audit_append({"venue_id": "mock-sky", "amount": 9000.0, "chain": "sepolia", "decision": "ESCALATE", "reason": "over per-period budget", "intent_key": "esc-test-1"})
    listed = plow.list_escalations()
    check("escalation listed", listed["count"] == 1 and listed["escalations"][0]["venue_id"] == "mock-sky", str(listed))

    async def run():
        return await plow.resolve_escalation(0, approve=False)

    r = asyncio.run(run())
    check("escalation rejected", r.get("decision") == "REJECTED", str(r))
    check("escalation no longer pending", plow.list_escalations()["count"] == 0)
    plow.AUDIT_DIR = os.path.join(os.path.dirname(__file__), "..", "audits")


def test_gate_window_enforced():
    """Outside the active window the gate DENYs before any transaction."""
    policy = {
        "window": {"start": 23, "end": 5},  # 23:00-05:00 UTC
        "functionAllowlist": ["deposit(uint256)"],
        "venues": [{"id": "v1", "name": "V1", "address": "0x1111111111111111111111111111111111111111", "tokenAddress": "0x2222222222222222222222222222222222222222", "enabled": True, "maxDeposit": 1000, "budget": 5000, "budgetPeriodHours": 24, "apyOverride": 5.0}],
    }
    for hour, expect_deny in [(12, True), (0, False), (3, False), (23, False), (4, False), (10, True)]:
        plow._utc_hour = lambda h=hour: h
        v = plow.gate_deposit(policy, "v1", 100.0, {"wouldRevert": False})
        check(f"window hour {hour} deny={expect_deny}", (v["decision"] == "DENY") == expect_deny, f"h={hour} -> {v['decision']} {v.get('reason')}")


def test_scheduler_picks_addressable_venue():
    """run_once must skip rank-only venues and pick the top addressable one."""
    import types

    calls = {"execute": None}

    async def fake_execute(venue_id, amount, **kw):
        calls["execute"] = (venue_id, amount)
        return {"ok": True, "decision": "ALLOW", "venue_id": venue_id, "txs": 2, "transaction_hash": "0x" + "ab" * 32}

    async def fake_scan(wallet):
        return {"chain": "sepolia", "positions": [{"symbol": "USDC", "amount": 5000.0}]}

    async def fake_rank():
        return {
            "chain": "sepolia",
            "ranked": [
                {"venue_id": "mock-spark", "name": "Mock Spark", "apy": 4.03, "addressable": False, "maxDeposit": 5000},
                {"venue_id": "mock-sky", "name": "Mock Sky Savings", "apy": 3.52, "addressable": True, "maxDeposit": 5000},
            ],
            "degraded": False,
            "poolCount": 0,
        }

    import importlib

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    sched = importlib.import_module("plow_scheduler")
    sched.scan_positions = fake_scan
    sched.rank_venues = fake_rank
    sched.execute_deposit = fake_execute
    r = asyncio.run(sched.run_once(max_deposit=1000.0, wallet="0x1776D4D751d97c85845bF54e6CE364CEc62D4bBf"))
    check("scheduler executed a deposit", r.get("decision") == "ALLOW", str(r))
    check("scheduler picked addressable venue", calls["execute"] == ("mock-sky", 1000.0), str(calls["execute"]))


if __name__ == "__main__":
    print("Plow server tests")
    test_stable_intent_key_deterministic()
    test_gate_deny_unlisted()
    test_gate_deny_unaddressed_venue()
    test_gate_deny_zero_amount()
    test_gate_deny_cap_exceeded()
    test_gate_deny_simulate_reverted()
    test_gate_deny_simulate_unavailable_fail_closed()
    test_gate_allow_in_policy()
    test_gate_escalate_over_budget()
    test_byok_precedence()
    test_abi_selector_deposit()
    test_rank_degrades_when_no_pools()
    test_rank_live_when_pools_match()
    test_scan_zero_positions_no_crash()
    test_escalation_lifecycle()
    test_gate_window_enforced()
    test_scheduler_picks_addressable_venue()
    print(f"\n{len(FAILURES)} failures" if FAILURES else "\nAll tests passed")
    sys.exit(1 if FAILURES else 0)
