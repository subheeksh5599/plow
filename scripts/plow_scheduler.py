#!/usr/bin/env python3
"""Plow scheduler — recurring yield placement loop.

Each cycle: scan the org wallet, rank venues by live APY, deposit into the top
venue up to its cap (within the policy budget), then sleep. Every action runs
through the same policy gate and lands in the audit trail.
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from plow import (  # noqa: E402
    execute_deposit,
    kh_wallet_address,
    rank_venues,
    scan_positions,
)

LOG = os.path.join(os.path.dirname(__file__), "..", "audits", "scheduler.log")


def _log(line):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    print(f"[{time.strftime('%H:%M:%S')}] {line}")


async def run_once(max_deposit: float, wallet: str) -> dict:
    scan = await scan_positions(wallet)
    if not scan["positions"]:
        _log(f"cycle: no idle positions ({scan['chain']}) — nothing to deposit")
        return {"action": "none", "reason": "no positions"}
    rank = await rank_venues()
    executable = [r for r in rank["ranked"] if r.get("addressable")]
    if not executable:
        _log("cycle: no executable ranked venues — nothing to deposit")
        return {"action": "none", "reason": "no executable venues"}
    top = executable[0]
    amount = min(max_deposit, float(top.get("maxDeposit", max_deposit)))
    if amount <= 0:
        return {"action": "none", "reason": "amount <= 0"}
    _log(f"cycle: top venue {top['venue_id']} @ {top['apy']:.2f}% — deposit {amount:,.2f}")
    result = await execute_deposit(top["venue_id"], amount, address=wallet)
    _log(f"cycle: decision={result.get('decision')} txs={result.get('txs')} tx={str(result.get('transaction_hash'))[:18]}")
    return result


async def loop(interval_hours: float, max_runs: int, max_deposit: float):
    wallet = await kh_wallet_address()
    _log(f"scheduler start: wallet={wallet} interval={interval_hours}h max_runs={max_runs} max_deposit={max_deposit}")
    runs = 0
    while max_runs == 0 or runs < max_runs:
        try:
            await run_once(max_deposit, wallet)
        except Exception as exc:
            _log(f"cycle error: {exc}")
        runs += 1
        if max_runs == 0 or runs < max_runs:
            _log(f"sleeping {interval_hours}h")
            await asyncio.sleep(interval_hours * 3600)
    _log("scheduler done")


def main():
    p = argparse.ArgumentParser(prog="plow-scheduler", description="Plow recurring yield placement")
    p.add_argument("--interval-hours", type=float, default=24.0)
    p.add_argument("--max-runs", type=int, default=0, help="0 = run forever")
    p.add_argument("--max-deposit", type=float, default=1000.0)
    args = p.parse_args()
    # load .env
    env = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env):
        for line in open(env):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    asyncio.run(loop(args.interval_hours, args.max_runs, args.max_deposit))


if __name__ == "__main__":
    main()
