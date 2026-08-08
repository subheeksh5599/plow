#!/usr/bin/env python3
"""Plow CLI — scan, rank, gate, deposit, verify from the terminal."""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from plow import (  # noqa: E402
    execute_deposit,
    kh_wallet_address,
    rank_venues,
    scan_positions,
    verify_position,
)


def _load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _print(label, obj):
    print(f"\n── {label} ──")
    print(json.dumps(obj, indent=2, default=str))


async def _scan(args):
    addr = args.address or await kh_wallet_address()
    _print("SCAN", await scan_positions(addr))
    _print("RANK", await rank_venues())


async def _deposit(args):
    result = await execute_deposit(args.venue, args.amount, address=args.address, auto_approve_escalation=args.approve)
    _print("DEPOSIT", result)


async def _verify(args):
    addr = args.address or await kh_wallet_address()
    _print("VERIFY", await verify_position(addr, args.venue))


def main():
    p = argparse.ArgumentParser(prog="plow", description="Plow — policy-gated yield deposits via KeeperHub")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan stablecoin positions + rank venues")
    s.add_argument("--address", help="wallet address (default: org KeeperHub wallet)")
    s.set_defaults(fn=_scan)

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

    args = p.parse_args()
    _load_env()
    asyncio.run(args.fn(args))


if __name__ == "__main__":
    main()
