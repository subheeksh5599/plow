#!/usr/bin/env python3
"""Plow CLI — scan, rank, gate, deposit, verify from the terminal.

Human-readable by default; pass --json for the raw structured output.
--chain selects the chain (env is set before the server module imports).
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

CHAIN_ENV = {
    "sepolia": {"KEEPERHUB_CHAIN": "sepolia", "KEEPERHUB_CHAIN_ID": "11155111"},
    "base-sepolia": {
        "KEEPERHUB_CHAIN": "base-sepolia",
        "KEEPERHUB_CHAIN_ID": "84532",
        "KEEPERHUB_RPC_OVERRIDE": "https://base-sepolia-rpc.publicnode.com",
        "PLOW_BLOCKSCOUT": "https://base-sepolia.blockscout.com/api",
        "PLOW_POLICY_PATH": "server/policies.base.json",
    },
}


def _load_env(path=".env"):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def _out_json(obj):
    print(json.dumps(obj, indent=2, default=str))


def _short(addr: str, n: int = 12) -> str:
    return f"{addr[:n]}…{addr[-4:]}"


async def _scan(args, plow):
    addr = args.address or await plow.kh_wallet_address()
    scan = await plow.scan_positions(addr)
    if args.json:
        _out_json(scan)
        return
    if not scan["positions"]:
        print(f"✓ scan {_short(addr)} — no idle positions on {scan['chain']}")
    for p in scan["positions"]:
        print(f"✓ read idle {p['symbol']:<5} {p['amount']:>12,.2f}  @ {_short(p['address'])}")
    print(f"→ {len(scan['positions'])} position(s) on {scan['chain']}")

    rank = await plow.rank_venues()
    if args.json:
        _out_json(rank)
        return
    print("→ rank venues (defillama yields, live)")
    for i, v in enumerate(rank["ranked"], 1):
        flag = " · degrade" if "degrade" in v["apySource"] else ""
        print(f"  {i}. {v['name']:<18} {v['apy']:>5.2f}%  apy{flag}")
    if rank["degraded"]:
        print("  (no live pools matched — configured rates, flagged)")


async def _rank(args, plow):
    rank = await plow.rank_venues()
    if args.json:
        _out_json(rank)
        return
    print("→ rank venues (defillama yields, live)")
    for i, v in enumerate(rank["ranked"], 1):
        flag = " · degrade" if "degrade" in v["apySource"] else ""
        print(f"  {i}. {v['name']:<18} {v['apy']:>5.2f}%  apy{flag}")
    if rank["degraded"]:
        print("  (no live pools matched — configured rates, flagged)")


async def _deposit(args, plow):
    result = await plow.execute_deposit(
        args.venue, args.amount, address=args.address, auto_approve_escalation=args.approve
    )
    if args.json:
        _out_json(result)
        return
    if result.get("decision") == "DENY":
        print(f"✗ DENY  {result.get('reason','')} · zero transactions broadcast")
        return
    if result.get("decision") == "ESCALATE":
        print(f"⚠ ESCALATE  {result.get('reason','')} · awaiting approval")
        return
    tx = result.get("transaction_hash") or ""
    print("· gate  venue allowlisted ✓  simulate: wouldRevert=false ✓")
    print(f"· approve exact {args.amount:,.2f} (no max-uint)   → sponsored {_short(tx) if tx else '…'}")
    print(f"· deposit {args.amount:,.2f} → {args.venue:<18} → sponsored {_short(tx)}")
    v = result.get("verified") or {}
    print(f"✓ verify balanceOf = {v.get('shares_formatted', 0):,.2f} sUSDS · onchain read")
    print("✓ audit  {decision:ALLOW, gas:sponsored, outcome:landed, ts:…}")


async def _verify(args, plow):
    addr = args.address or await plow.kh_wallet_address()
    result = await plow.verify_position(addr, args.venue)
    if args.json:
        _out_json(result)
        return
    if result.get("ok"):
        print(f"✓ verify {_short(addr)} in {args.venue}: {result.get('shares_formatted', 0):,.2f} sUSDS · {result.get('source')}")
    else:
        print(f"✗ verify failed: {result.get('error','')}")


async def _escalations(args, plow):
    result = plow.list_escalations()
    if args.json:
        _out_json(result)
        return
    if not result["escalations"]:
        print("✓ no pending escalations")
    for e in result["escalations"]:
        print(f"⚠ [{e['index']}] {e['venue_id']} {e['amount']:,.2f} · {e.get('reason','')}")


async def _resolve(args, plow):
    result = await plow.resolve_escalation(args.index, args.approve)
    if args.json:
        _out_json(result)
        return
    print(f"✓ {result.get('decision')}  {result.get('reason', result.get('error',''))}")


def main():
    p = argparse.ArgumentParser(prog="plow", description="Plow — policy-gated yield deposits via KeeperHub")
    p.add_argument("--json", action="store_true", help="raw structured output")
    p.add_argument("--chain", choices=list(CHAIN_ENV), default=None, help="chain (env is set before the server imports)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan stablecoin positions + rank venues")
    s.add_argument("--address", help="wallet address (default: org KeeperHub wallet)")
    s.set_defaults(fn=_scan)

    r = sub.add_parser("rank", help="rank allowlisted venues by APY")
    r.set_defaults(fn=_rank)

    d = sub.add_parser("deposit", help="policy-gated deposit")
    d.add_argument("--venue", required=True)
    d.add_argument("--amount", type=float, required=True)
    d.add_argument("--address")
    d.add_argument("--approve", action="store_true", help="auto-approve ESCALATE decisions")
    d.set_defaults(fn=_deposit)

    v = sub.add_parser("verify", help="verify onchain position")
    v.add_argument("--venue", required=True)
    v.add_argument("--address")
    v.set_defaults(fn=_verify)

    e = sub.add_parser("escalations", help="list pending ESCALATE decisions")
    e.set_defaults(fn=_escalations)

    r2 = sub.add_parser("resolve", help="approve/reject a pending escalation")
    r2.add_argument("--index", type=int, required=True)
    r2.add_argument("--approve", action="store_true", help="approve (re-run gated deposit)")
    r2.add_argument("--reject", action="store_true", help="reject")
    r2.set_defaults(fn=_resolve)

    args = p.parse_args()
    _load_env()
    if args.chain:
        for k, val in CHAIN_ENV[args.chain].items():
            os.environ[k] = val

    import plow  # env is set before import → chain constants are correct

    asyncio.run(args.fn(args, plow))


if __name__ == "__main__":
    main()
