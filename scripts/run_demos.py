#!/usr/bin/env python3
"""Plow live demo runner — mints seed capital, then runs scan -> rank -> gate ->
deposit (ALLOW + DENY) -> verify through KeeperHub on Sepolia. Writes evidence JSON."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from plow import (  # noqa: E402
    ABI_MOCK_USDC,
    CHAIN,
    CHAIN_ID,
    audit_append,
    execute_deposit,
    kh_contract_call,
    kh_execution_status,
    kh_wallet_address,
    rank_venues,
    scan_positions,
    verify_position,
)

MOCK_USDC = os.environ.get("PLOW_MOCK_USDC", "0x032b4f813F0E21bAD8B6Bd497a8a6841B8a28dd9")
ORG = os.environ.get("PLOW_ORG_WALLET", "0x1776D4D751d97c85845bF54e6CE364CEc62D4bBf")
MINT_AMOUNT = 10_000  # USDC
DEPOSIT_AMOUNT = 1_000.0
DENY_VENUE = "unlisted-venue"


def _load_env(path=".env"):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


async def main():
    evidence = {"chain": CHAIN, "chainId": CHAIN_ID, "org_wallet": ORG, "runs": []}

    # ---- run 0: mint seed capital (sponsored contract-call, simulate first) — skip if already funded
    print("== 0. mint seed MockUSDC to org wallet ==")
    scan0 = await scan_positions(ORG)
    held = next((p["amount"] for p in scan0["positions"] if p["symbol"] == "USDC"), 0.0)
    if held >= MINT_AMOUNT:
        print(f"   already funded ({held} USDC) — skipping mint")
        evidence["runs"].append({"run": 0, "action": f"mint {MINT_AMOUNT} MockUSDC", "skipped": True, "held": held})
    else:
        sim = await kh_contract_call(MOCK_USDC, "mint", [ORG, MINT_AMOUNT * 10**6], ABI_MOCK_USDC, simulate=True)
        print("   simulate:", {k: sim.get(k) for k in ("status", "gasEstimate", "wouldRevert")})
        if sim.get("wouldRevert") is not False:
            print("   FAIL: mint simulate reverted"); sys.exit(1)
        exec_mint = await kh_contract_call(MOCK_USDC, "mint", [ORG, MINT_AMOUNT * 10**6], ABI_MOCK_USDC)
        mint_id = exec_mint.get("executionId")
        mint_status = await kh_execution_status(mint_id)
        evidence["runs"].append({"run": 0, "action": f"mint {MINT_AMOUNT} MockUSDC -> org wallet", "executionId": mint_id, "tx": mint_status.get("transactionHash"), "link": mint_status.get("transactionLink"), "sponsored": mint_status.get("sponsored")})
        print(f"   mint tx: {mint_status.get('transactionHash')} sponsored={mint_status.get('sponsored')}")

    # ---- run 1: scan
    print("\n== 1. scan_positions ==")
    scan = await scan_positions(ORG)
    print(f"   positions: {scan['positions']}")
    evidence["runs"].append({"run": 1, "action": "scan_positions", "result": scan["positions"]})

    # ---- run 2: rank
    print("\n== 2. rank_venues ==")
    rank = await rank_venues()
    for v in rank["ranked"]:
        print(f"   {v['apy']:>5}%  {v['name']:<18} {v['apySource']}")
    print(f"   degraded={rank['degraded']} pools={rank['poolCount']}")
    evidence["runs"].append({"run": 2, "action": "rank_venues", "degraded": rank["degraded"], "poolCount": rank["poolCount"], "ranked": rank["ranked"]})

    # ---- run 3: gated deposit (ALLOW path)
    print(f"\n== 3. execute_deposit mock-sky {DEPOSIT_AMOUNT} ==")
    dep = await execute_deposit("mock-sky", DEPOSIT_AMOUNT, address=ORG)
    print(f"   decision={dep.get('decision')} reason={dep.get('reason')}")
    print(f"   tx={dep.get('transaction_hash')} sponsored={dep.get('sponsored')}")
    print(f"   verified={dep.get('verified')}")
    evidence["runs"].append({"run": 3, "action": "deposit ALLOW mock-sky", "decision": dep.get("decision"), "tx": dep.get("transaction_hash"), "link": dep.get("transaction_link"), "sponsored": dep.get("sponsored"), "verified": dep.get("verified"), "shares": dep.get("verified", {}).get("shares_formatted")})

    # ---- run 4: DENY path (zero txs)
    print(f"\n== 4. execute_deposit {DENY_VENUE} (out of policy) ==")
    deny = await execute_deposit(DENY_VENUE, 100.0, address=ORG)
    print(f"   decision={deny.get('decision')} reason={deny.get('reason')} txs={deny.get('txs')}")
    evidence["runs"].append({"run": 4, "action": "deposit DENY unlisted-venue", "decision": deny.get("decision"), "reason": deny.get("reason"), "txs": deny.get("txs")})

    # ---- run 5: verify
    print("\n== 5. verify_position ==")
    verified = await verify_position(ORG, "mock-sky")
    print(f"   shares={verified.get('shares_formatted')} sUSDS source={verified.get('source')}")
    evidence["runs"].append({"run": 5, "action": "verify_position", "result": verified})

    # ---- run 6: wallet balance (gas affordability note)
    print("\n== 6. org wallet balance ==")
    bal = await _native_balance()
    print(f"   {bal} ETH")
    evidence["runs"].append({"run": 6, "action": "org wallet ETH balance", "eth": bal})

    with open(os.path.join(os.path.dirname(__file__), "..", "evidence.json"), "w") as f:
        json.dump(evidence, f, indent=2)
    print("\nEvidence written to evidence.json")


async def _native_balance() -> float:
    import httpx
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"https://eth-sepolia.blockscout.com/api?module=account&action=balance&address={ORG}")
        return float(r.json().get("result", 0)) / 1e18


if __name__ == "__main__":
    _load_env()
    asyncio.run(main())
