#!/usr/bin/env python3
"""Plow live demo runner — scan -> rank -> gate -> deposit (ALLOW + DENY) ->
verify through KeeperHub, on sepolia or base-sepolia. Writes evidence JSON."""
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
    p = argparse.ArgumentParser(description="Plow live demo runner")
    p.add_argument("--chain", default="sepolia", choices=["sepolia", "base-sepolia"])
    p.add_argument("--mint", type=float, default=10_000.0)
    p.add_argument("--deposit", type=float, default=1_000.0)
    p.add_argument("--deny-venue", default="unlisted-venue")
    p.add_argument("--deposit-venue", default="mock-sky")
    args = p.parse_args()

    _load_env()
    os.environ["KEEPERHUB_CHAIN"] = args.chain
    if args.chain == "base-sepolia":
        os.environ["KEEPERHUB_CHAIN_ID"] = "84532"
        os.environ["KEEPERHUB_RPC_OVERRIDE"] = "https://base-sepolia-rpc.publicnode.com"
        os.environ["PLOW_POLICY_PATH"] = os.path.join("server", "policies.base.json")
        os.environ["PLOW_BLOCKSCOUT"] = "https://base-sepolia.blockscout.com/api"

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))
    import plow  # env is set before import → CHAIN/CHAIN_ID/RPC are correct

    ORG = os.environ.get("PLOW_ORG_WALLET", "0x1776D4D751d97c85845bF54e6CE364CEc62D4bBf")
    MINT_AMOUNT = args.mint
    DEPOSIT_AMOUNT = args.deposit

    async def run():
        evidence = {"chain": plow.CHAIN, "chainId": plow.CHAIN_ID, "org_wallet": ORG, "runs": []}

        print(f"== 0. mint seed MockUSDC on {args.chain} ==")
        scan0 = await plow.scan_positions(ORG)
        held = next((pp["amount"] for pp in scan0["positions"] if pp["symbol"] == "USDC"), 0.0)
        if held >= MINT_AMOUNT:
            print(f"   already funded ({held} USDC) — skipping mint")
            evidence["runs"].append({"run": 0, "action": f"mint {MINT_AMOUNT} MockUSDC", "skipped": True, "held": held})
        else:
            sim = await plow.kh_contract_call(plow.MOCK_USDC, "mint", [ORG, int(MINT_AMOUNT * 10**6)], plow.ABI_MOCK_USDC, simulate=True)
            print("   simulate:", {k: sim.get(k) for k in ("status", "gasEstimate", "wouldRevert")})
            if sim.get("wouldRevert") is not False:
                print("   FAIL: mint simulate reverted")
                sys.exit(1)
            exec_mint = await plow.kh_contract_call(plow.MOCK_USDC, "mint", [ORG, int(MINT_AMOUNT * 10**6)], plow.ABI_MOCK_USDC)
            mint_id = exec_mint.get("executionId")
            mint_status = await plow.kh_execution_status(mint_id)
            evidence["runs"].append({"run": 0, "action": f"mint {MINT_AMOUNT} MockUSDC -> org wallet", "executionId": mint_id, "tx": mint_status.get("transactionHash"), "link": mint_status.get("transactionLink"), "sponsored": mint_status.get("sponsored")})
            print(f"   mint tx: {mint_status.get('transactionHash')} sponsored={mint_status.get('sponsored')}")

        print("\n== 1. scan_positions ==")
        scan = await plow.scan_positions(ORG)
        for pp in scan["positions"]:
            print(f"   {pp['symbol']:<5} {pp['amount']:>12,.2f} @ {pp['address'][:10]}")
        evidence["runs"].append({"run": 1, "action": "scan_positions", "result": scan})

        print("\n== 2. rank_venues ==")
        rank = await plow.rank_venues()
        for v in rank["ranked"]:
            flag = " · degrade" if "degrade" in v["apySource"] else ""
            print(f"   {v['apy']:>5.2f}%  {v['name']:<18}{flag}")
        print(f"   degraded={rank['degraded']} pools={rank['poolCount']}")
        evidence["runs"].append({"run": 2, "action": "rank_venues", "result": rank})

        print(f"\n== 3. execute_deposit {args.deposit_venue} {DEPOSIT_AMOUNT:.0f} ==")
        dep = await plow.execute_deposit(args.deposit_venue, DEPOSIT_AMOUNT, address=ORG)
        print(f"   decision={dep.get('decision')} reason={dep.get('reason')}")
        if dep.get("ok"):
            print(f"   tx={dep.get('transaction_hash')} sponsored={dep.get('sponsored')}")
            print(f"   verified={dep.get('verified')}")
        evidence["runs"].append({"run": 3, "action": f"deposit {dep.get('decision')} {args.deposit_venue}", "tx": dep.get("transaction_hash"), "sponsored": dep.get("sponsored"), "decision": dep.get("decision"), "txs": dep.get("txs"), "shares": (dep.get("verified") or {}).get("shares_formatted")})

        print(f"\n== 4. execute_deposit {args.deny_venue} (out of policy) ==")
        deny = await plow.execute_deposit(args.deny_venue, 100.0, address=ORG)
        print(f"   decision={deny.get('decision')} reason={deny.get('reason')} txs={deny.get('txs')}")
        evidence["runs"].append({"run": 4, "action": f"deposit {deny.get('decision')} {args.deny_venue}", "decision": deny.get("decision"), "reason": deny.get("reason"), "txs": deny.get("txs")})

        print(f"\n== 5. verify_position ==")
        ver = await plow.verify_position(ORG, args.deposit_venue)
        print(f"   shares={ver.get('shares_formatted')} sUSDS source={ver.get('source')}")
        evidence["runs"].append({"run": 5, "action": "verify_position", "result": ver})

        print("\n== 6. org wallet ETH balance ==")
        bal = await plow.rpc_native_balance(ORG)
        print(f"   {bal:.4f} ETH")
        evidence["runs"].append({"run": 6, "action": "org wallet ETH balance", "eth": bal})

        with open(os.path.join(os.path.dirname(__file__), "..", f"evidence-{args.chain}.json"), "w") as f:
            json.dump(evidence, f, indent=2, default=str)
        print(f"\nEvidence written to evidence-{args.chain}.json")

    asyncio.run(run())


if __name__ == "__main__":
    main()
