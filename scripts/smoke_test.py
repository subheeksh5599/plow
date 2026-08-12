#!/usr/bin/env python3
"""Smoke-test the deployed Plow API.

Checks /api/health, MCP tools/list, and a live rank_venues call through the
deployed endpoint with BYOK. Uses the same JSON-RPC shape the MCP server speaks.

Usage:
    KH_API_KEY=kh_... .venv/bin/python scripts/smoke_test.py [--url https://plow-beta.vercel.app]
"""
import argparse
import json
import os
import sys

import httpx

URL = os.environ.get("PLOW_SMOKE_URL", "https://plow-beta.vercel.app")


def rpc(client: httpx.Client, url: str, key: str, method: str, params: dict | None = None) -> dict:
    resp = client.post(
        f"{url}/api/plow",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=URL)
    args = p.parse_args()
    key = os.environ.get("KH_API_KEY", "")
    if not key:
        print("✗ KH_API_KEY not set — set it to your KeeperHub org key")
        sys.exit(1)

    with httpx.Client() as client:
        health = client.get(f"{args.url}/api/health", timeout=20)
        health.raise_for_status()
        assert health.json().get("ok") is True, f"health: {health.json()}"
        print(f"✓ /api/health ok — {health.json().get('service')} on {health.json().get('chain')}")

        tools = rpc(client, args.url, key, "tools/list")
        names = [t["name"] for t in tools["result"]["tools"]]
        expected = {"scan_positions", "rank_venues", "execute_deposit", "execute_withdraw", "verify_position", "list_escalations", "resolve_escalation"}
        assert expected.issubset(set(names)), f"missing tools: {expected - set(names)}"
        print(f"✓ tools/list — {len(names)} tools: {', '.join(names)}")

        rank = rpc(client, args.url, key, "tools/call", {"name": "rank_venues", "arguments": {}})
        # MCP spec: tool results are content blocks — unwrap the JSON text.
        blocks = rank["result"].get("content", [])
        ranked = json.loads(blocks[0]["text"])["ranked"] if blocks else rank["result"].get("ranked", [])
        assert ranked, "rank_venues returned no venues"
        top = ranked[0]
        print(f"✓ rank_venues live — top: {top['name']} {top['apy']:.2f}% ({top['apySource'][:50]})")

    print("\nsmoke test PASS")


if __name__ == "__main__":
    main()
