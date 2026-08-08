#!/usr/bin/env python3
"""Plow live demo runner — scan -> rank -> gate -> supply/withdraw (Aave V3
Sepolia, WETH) -> verify, plus a zero-tx DENY, all through KeeperHub.

Writes evidence-<chain>.json. The asset (WETH) is seeded dev-side (wrap +
transfer); every execution step runs through KeeperHub sponsored.
"""
import argparse
import asyncio
import json
import os
import sys


def _load_env(path=".env"):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def main():
    p = argparse.ArgumentParser(description="Plow live demo runner (real Aave V3 Sepolia)")
    p.add_argument("--chain", default="sepolia", choices=["sepolia", "base-sepolia"])
    p.add_argument("--deposit", type=float, default=0.005)
    p.add_argument("--withdraw", type=float, default=0.002)
    p.add_argument("--deny-venue", default="unlisted-venue")
    p.add_argument("--deposit-venue", default="aave-v3-weth")
    args = p.parse_args()

    _load_env()
    os.environ["KEEPERHUB_CHAIN"] = args.chain
    if args.chain == "base-sepolia":
        os.environ["KEEPERHUB_CHAIN_ID"] = "84532"
        os.environ["KEEPERHUB_RPC_OVERRIDE"] = "https://base-sepolia-rpc.publicnode.com"
        os.environ["PLOW_POLICY_PATH"] = os.path.join("server", "policies.base.json")
        os.environ["PLOW_BLOCKSCOUT"] = "https://base-sepolia.blockscout.com/api"

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
    import plow  # env is set before import → chain constants are correct

    ORG = os.environ.get("PLOW_ORG_WALLET", "0x1776D4D751d97c85845bF54e6CE364CEc62D4bBf")

    async def run():
        evidence = {"chain": plow.CHAIN, "chainId": plow.CHAIN_ID, "org_wallet": ORG, "runs": []}

        print(f"== 1. scan_positions ({args.chain}) ==")
        scan = await plow.scan_positions(ORG)
        for pos in scan["positions"]:
            print(f"   {pos['symbol']:<5} {pos['amount']:>12,.6f} @ {pos['address'][:10]}")
        evidence["runs"].append({"run": 1, "action": "scan_positions", "result": scan})

        print("\n== 2. rank_venues (live DefiLlama) ==")
        rank = await plow.rank_venues()
        for v in rank["ranked"]:
            print(f"   {v['apy']:>5.2f}%  {v['name']:<22} {v['apySource']}")
        evidence["runs"].append({"run": 2, "action": "rank_venues", "result": rank})

        print(f"\n== 3. execute_deposit {args.deposit_venue} {args.deposit} WETH (supply) ==")
        dep = await plow.execute_deposit(args.deposit_venue, args.deposit, address=ORG)
        print(f"   decision={dep.get('decision')} reason={dep.get('reason')}")
        if dep.get("ok"):
            print(f"   approve={dep.get('approve_tx')}")
            print(f"   tx={dep.get('transaction_hash')} sponsored={dep.get('sponsored')}")
            print(f"   verified={dep.get('verified')}")
        evidence["runs"].append({"run": 3, "action": f"deposit {dep.get('decision')} {args.deposit_venue}", "approve_tx": dep.get("approve_tx"), "tx": dep.get("transaction_hash"), "sponsored": dep.get("sponsored"), "decision": dep.get("decision"), "txs": dep.get("txs"), "shares": (dep.get("verified") or {}).get("shares_formatted")})

        print(f"\n== 4. execute_withdraw {args.deposit_venue} {args.withdraw} WETH ==")
        wd = await plow.execute_withdraw(args.deposit_venue, args.withdraw, address=ORG)
        print(f"   decision={wd.get('decision')} reason={wd.get('reason')}")
        if wd.get("ok"):
            print(f"   tx={wd.get('transaction_hash')} sponsored={wd.get('sponsored')}")
        evidence["runs"].append({"run": 4, "action": f"withdraw {wd.get('decision')} {args.deposit_venue}", "tx": wd.get("transaction_hash"), "sponsored": wd.get("sponsored"), "decision": wd.get("decision"), "txs": wd.get("txs")})

        print(f"\n== 5. execute_deposit {args.deny_venue} (out of policy) ==")
        deny = await plow.execute_deposit(args.deny_venue, 0.001, address=ORG)
        print(f"   decision={deny.get('decision')} reason={deny.get('reason')} txs={deny.get('txs')}")
        evidence["runs"].append({"run": 5, "action": f"deposit {deny.get('decision')} {args.deny_venue}", "decision": deny.get("decision"), "reason": deny.get("reason"), "txs": deny.get("txs")})

        print(f"\n== 6. verify_position ==")
        ver = await plow.verify_position(ORG, args.deposit_venue)
        print(f"   aWETH={ver.get('shares_formatted')} source={ver.get('source')}")
        evidence["runs"].append({"run": 6, "action": "verify_position", "result": ver})

        print("\n== 7. org wallet WETH balance ==")
        bal = await plow.rpc_read_erc20("0xc558dbdd856501fcd9aaf1e62eae57a9f0629a3c", ORG)
        print(f"   {bal / 1e18:.6f} WETH")
        evidence["runs"].append({"run": 7, "action": "org wallet WETH balance", "weth": bal / 1e18})

        with open(os.path.join(os.path.dirname(__file__), "..", f"evidence-{args.chain}.json"), "w") as f:
            json.dump(evidence, f, indent=2, default=str)
        print(f"\nEvidence written to evidence-{args.chain}.json")

    asyncio.run(run())


if __name__ == "__main__":
    main()
