<div align="center">

<img src="docs/media/landing.png" alt="Plow — policy-gated yield execution on KeeperHub" width="100%" />

&nbsp;

[![Live demo](https://img.shields.io/badge/●_live-plow-beta.vercel.app-533afd)](https://plow-beta.vercel.app)
[![Aave V3 Pool (Sepolia)](https://img.shields.io/badge/📜_Aave_V3_Pool_Sepolia-14151a)](https://sepolia.etherscan.io/address/0x6Ae43d3271ff6888e7Fc43Fd7321a503ff738951)
[![License: MIT](https://img.shields.io/badge/license-MIT-533afd.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-21%20passing-3fb950)](https://github.com/subheeksh5599/plow/actions)
[![CI](https://img.shields.io/github/actions/workflow/status/subheeksh5599/plow/ci.yml?branch=main&label=CI)](https://github.com/subheeksh5599/plow/actions)
![Stack](https://img.shields.io/badge/Python%20·%20Next.js-1f1f23)
![KeeperHub](https://img.shields.io/badge/KeeperHub-execution%20layer-533afd)
![Sepolia](https://img.shields.io/badge/Sepolia-testnet-533afd)

### Put idle capital to work, autonomously.

Plow is the write path for agent-executed yield. It scans a wallet's idle
positions, ranks allowlisted venues by **live DefiLlama APY**, and supplies the
top venue through KeeperHub — policy-gated, gas-sponsored, verified onchain,
and fully audited. No mocks, no fallback rates, no fabricated data.

### ▶ Live now at **[plow-beta.vercel.app](https://plow-beta.vercel.app)**

**[ Live demo ↗ ](https://plow-beta.vercel.app)** · **[ Aave V3 Pool on Etherscan ↗ ](https://sepolia.etherscan.io/address/0x6Ae43d3271ff6888e7Fc43Fd7321a503ff738951)** · **[ Transactions ↓ ](#transactions--the-evidence)** · **[ Run it locally ↓ ](#run-it-locally)**

Built for the **KeeperHub Agents Onchain Hackathon**. MIT licensed.

</div>

---

## Table of contents

- [▶ See it in one command](#-see-it-in-one-command)
- [The problem Plow solves](#the-problem-plow-solves)
- [How Plow works](#how-plow-works)
  - [1 · Scan](#1--scan)
  - [2 · Rank](#2--rank)
  - [3 · Gate](#3--gate)
  - [4 · Execute and verify](#4--execute-and-verify)
- [Transactions — the evidence](#transactions--the-evidence)
- [Architecture](#architecture)
  - [Transaction flow](#transaction-flow)
  - [Component by component](#component-by-component)
- [Engineering decisions — the hard problems](#engineering-decisions--the-hard-problems)
- [What's real vs pending — the honesty table](#whats-real-vs-pending--the-honesty-table)
- [Tests](#tests)
- [Run it locally](#run-it-locally)
- [Deploy](#deploy)
- [Project layout](#project-layout)
- [Tech stack](#tech-stack)
- [Roadmap](#roadmap)
- [License](#license)

---

## ▶ See it in one command

Plow is a CLI. One address in, a live Aave position out — every step executed
through KeeperHub and logged:

```bash
$ plow scan 0x1776D4D751d97c85845bF54e6CE364CEc62D4bBf --chain sepolia
✓ read idle WETH      0.01  @ 0xc558dbdd85…9a3c
→ 1 position(s) on sepolia

$ plow rank
→ rank venues (defillama yields, live)
  1. Aave V3 (WETH supply)  1.43%  apy

$ plow deposit --venue aave-v3-weth --amount 0.005
· gate  venue allowlisted ✓  simulate: wouldRevert=false ✓
· deposit 0.005 → aave-v3-weth        → sponsored 0x06d9288e…26f
✓ verify balanceOf = 0.005 aWETH · onchain read
✓ audit  {decision:ALLOW, gas:sponsored, outcome:landed, ts:…}

$ plow deposit --venue unlisted-venue --amount 0.001
✗ DENY  venue unlisted-venue disabled · zero transactions broadcast
```

Every hash is real and on Sepolia right now. The sponsored supply landed
[0x06d9288e…26f](https://sepolia.etherscan.io/tx/0x06d9288e821f98adc86128cfc99e941157f6350f59de80df24f0c5597b0f826f)
into the real [Aave V3 Pool](https://sepolia.etherscan.io/address/0x6Ae43d3271ff6888e7Fc43Fd7321a503ff738951),
and the onchain read-back confirms **0.005 aWETH** in the org wallet. The
withdraw returned funds with matching arithmetic. No mock contracts anywhere.

---

## The problem Plow solves

The automation funnel stops at the read. Scanners rank the venue, show the APY —
and nothing happens. KeeperHub's own scan-to-automate spec says it in writing:
*"Read-only: Yes. No deposit/approve/write node is produced. The auto-deposit
write path is the deferred Phase 999.1 backlog item."*

- **Idle positions earn nothing** while the same asset earns live APY in a
  supply venue — the distance between them is one transaction
- **Scanners recommend, nothing executes** — the suggestion engine is a dead
  end by design
- **Agents shouldn't supply blind** — deposits need a policy gate, exact
  approvals, and an audit trail, not a raw `supply()`
- **No write path exists for agents** — that is the gap Plow fills

---

## How Plow works

Four capabilities, executed end to end through KeeperHub on Sepolia, into the
real Aave V3 Pool at
[0x6Ae43d32…8951](https://sepolia.etherscan.io/address/0x6Ae43d3271ff6888e7Fc43Fd7321a503ff738951).

### 1 · Scan

`eth_call` reads resolve every position across the configured tokens — the same
methodology as KeeperHub's own scanner. Balances are read onchain, never
assumed:

```python
positions = await scan_positions(org_wallet)
# [{'symbol': 'WETH', 'amount': 0.01, 'source': 'eth_call balanceOf'}]
```

### 2 · Rank

Allowlisted venues are ranked by **live DefiLlama APY** (15-min cache). There is
no fallback: if the yield feed is unreachable the call fails loudly, and a
venue whose pool cannot be matched is excluded — **nothing is ever ranked on a
made-up rate**:

```python
ranked = await rank_venues()
# [{'venue_id': 'aave-v3-weth', 'apy': 1.43, 'apySource': 'defillama aave-v3/WETH tvl=$723,338,851'}]
```

### 3 · Gate

The supply is a proposal, not an order. A **pre-gate** (allowlist, amount cap,
per-period budget, active window) runs before any transaction exists — out of
policy means **zero broadcasts**. Then the exact approval and the supply are
each simulated first (`wouldRevert` must be `false`), and approvals are exact
amounts only, per KeeperHub's PREFILL-07 — never max-uint:

```python
verdict = gate_deposit(policy, venue_id, amount, simulate)
# ALLOW / DENY / ESCALATE — with the full check list in the audit trail
```

### 4 · Execute and verify

In-policy supplies execute as gas-sponsored `contract-call`s (every write is
`"sponsored": true` on testnets), then the aToken balance is read back onchain
as proof:

```python
result = await execute_deposit("aave-v3-weth", 0.005)
# decision=ALLOW  sponsored=True  verified={'shares_formatted': 0.005}
```

---

## Transactions — the evidence

Every run lands real transactions on Sepolia against the real Aave V3 Pool,
each verified status 1 on the explorer. The DENY row is proof too — the stop
broadcast nothing.

| Run | Action | Transaction | Status |
|---|---|---|---|
| Seed | Fund deploy EOA (sponsored org → EOA) | [0xae2824a8…11d](https://sepolia.etherscan.io/tx/0xae2824a8089bdf4e86fce4b75dbca8620d4cfb8f35460f21b6ffcdc0fe46311d) | ✅ sponsored |
| Seed | Wrap 0.01 ETH → WETH (dev EOA) | [0x955d293c…720](https://sepolia.etherscan.io/tx/0x955d293c3712c9fb604b6e6204b4e3a6b5f279dfc30cd8d24c549923b1cac720) | ✅ dev EOA |
| Seed | WETH → org wallet (dev EOA) | [0x91c4caac…325](https://sepolia.etherscan.io/tx/0x91c4caac317b02b9cb06c5ca8599e5abaa687b4b2e7846df0a76efc51ec67325) | ✅ dev EOA |
| 01 | Scan + rank — live Aave V3 WETH APY | onchain reads | ✅ 1.43% (DefiLlama) |
| 02 | **Supply 0.005 WETH → Aave V3** | [0x06d9288e…26f](https://sepolia.etherscan.io/tx/0x06d9288e821f98adc86128cfc99e941157f6350f59de80df24f0c5597b0f826f) | ✅ **sponsored** |
| 03 | **Withdraw 0.002 WETH from Aave V3** | [0x41d8900d…88f](https://sepolia.etherscan.io/tx/0x41d8900d160bf3f8accd56c4ea04751de7393bd2df2fff3d22c0f5951d9288f1) | ✅ **sponsored** |
| 04 | Supply to unlisted venue | **zero txs** | ✅ blocked — the stop is the proof |
| 05 | verify_position aWETH read-back | onchain read | ✅ 0.003 aWETH (0.005 − 0.002) |

<img src="docs/media/2.png" alt="Position balance — verified onchain after each step" width="100%" />

<img src="docs/media/3.png" alt="Gated execution — ALLOW lands, DENY broadcasts nothing" width="100%" />

---

## Architecture

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐
│   plow CLI   │──▶│  scan + rank │──▶│  policy gate │──▶│  KeeperHub API  │
│  (scripts/)  │   │  (server/)   │   │  (server/)   │   │  execute/       │
│  MCP tools   │   │  RPC reads   │   │  ALLOW/DENY/ │   │  contract-call  │
│              │   │  defillama   │   │  ESCALATE    │   │  (sponsored)    │
└──────────────┘   └──────┬───────┘   └──────┬───────┘   └────────┬────────┘
                          │                  │                     │
                          ▼                  ▼                     ▼
                   Sepolia RPC          audit trail          Aave V3 Pool
                   eth_call reads       (JSONL)              (real protocol)
                                                              + WETH/aWETH
```

### Transaction flow

1. **Scan** — `eth_call balanceOf` reads the wallet's positions
2. **Rank** — venues ranked by live DefiLlama APY (no fallback)
3. **Pre-gate** — allowlist, amount cap, per-period budget, active window — zero txs spent
4. **Approve exact** — simulate, then `approve(pool, exactAmount)` via KeeperHub (sponsored)
5. **Simulate supply** — `wouldRevert: false` required, else DENY (fail closed)
6. **Gate** — full check list evaluated; ALLOW / DENY / ESCALATE recorded to the audit trail
7. **Supply** — `supply(asset, amount, onBehalfOf, 0)` on the Aave V3 Pool (sponsored)
8. **Verify** — aToken `balanceOf` read-back onchain confirms the position
9. **Audit** — every decision logged: trigger, simulation, tx, gas, sponsored, outcome

### Component by component

| Component | Technology | Responsibility |
|---|---|---|
| Plow server | Python 3.12, httpx | KeeperHub REST client, BYOK, policy gate, scan/rank engine, audit store |
| MCP surface | JSON-RPC over HTTP | `scan_positions`, `rank_venues`, `execute_deposit`, `execute_withdraw`, `verify_position`, `list_escalations`, `resolve_escalation` |
| plow CLI | Python, argparse | Terminal demo path — same functions as the MCP tools |
| plow scheduler | Python | Recurring scan → rank → gated deposit loop (`scripts/plow_scheduler.py`) |
| Venue | Aave V3 (Sepolia Pool) | Real protocol: `supply` / `withdraw` on WETH reserve; aToken for verification |
| KeeperHub | Direct-execution API | Sponsored contract-calls, execution status, audit evidence |
| Frontend | Next.js 16 static export | Landing page with capital-flow hero, live-flow terminal, evidence table |

---

## Engineering decisions — the hard problems

**1. The supply simulates reverting until the approval exists — so the order
matters.** Simulating `supply()` before `approve()` returns `ERC20: insufficient
allowance` and the gate DENYs a perfectly good deposit. Plow's order is:
pre-gate (zero txs) → exact approve → re-simulate supply → full gate → supply.
A value-moving action is never simulated against state the agent hasn't set up.

**2. DENY must cost zero transactions.** The first version approved first and
gated second — an out-of-policy venue still burned a sponsored approve. The
pre-gate (allowlist, cap, budget, window) now runs before any transaction
exists. The evidence table shows the fix: DENY row = zero txs.

**3. KeeperHub contract-calls route through the sponsor's relayer — `to` lies.**
Every sponsored contract-call transaction is signed by the relayer, so the tx
record's `to` is the relayer, not the target contract. Onchain proof therefore
comes from the execution status (`sponsored: true`, target in calldata) **plus**
the aToken `balanceOf` read-back on the actual venue — never from the tx `to`
field alone.

**4. A reverting simulation returns HTTP 4xx with a structured body.**
KeeperHub's simulate gate returns `wouldRevert: true` as a 4xx envelope, not a
200. The client treats any 4xx containing `wouldRevert` as a structured
simulation result — and the gate DENYs it.

**5. KeeperHub has no deploy API — testnet asset seeding is dev-side, every
execution step is KeeperHub's.** The venue contracts (real protocol, no custom
deploys) and test assets are seeded with a throwaway EOA: one sponsored org →
EOA transfer, an ETH→WETH wrap, and a WETH transfer to the org wallet. The
agent itself never holds a private key; approve, supply, withdraw and every
value-moving action execute through KeeperHub's custody, sponsored.

**6. There is no fallback APY — the rank fails loudly instead.** A yield bot
that silently substitutes stale or configured rates when the feed is down is
just a fake-data pipeline. `rank_venues` requires the live DefiLlama feed
(fetch failure → error) and excludes any venue without a matching live pool.
Nothing is ever ranked on a made-up number.

**7. A ranked venue is not an executable venue.** Rank-only entries (no
executable address) appear in APY context but the gate DENYs any supply to
them — zero txs — and the scheduler only ever picks addressable venues.

**8. Testnet stablecoin reserves on Aave are supply-capped.** USDC/USDT/DAI
supply on Aave V3 Sepolia reverts. Plow supplies the **WETH reserve** (open
cap), seeded by a real ETH→WETH wrap. The APY shown is the real live Aave V3
WETH rate from DefiLlama.

---

## What's real vs pending — the honesty table

| Feature | Status | Detail |
|---|---|---|
| Position scan | ✅ Real | `eth_call balanceOf` reads on Sepolia |
| APY ranking | ✅ Real | LIVE DefiLlama pool (Aave V3 WETH, TVL shown); no fallback — feed failure fails loudly |
| Policy gate | ✅ Real | Allowlist, cap, budget, window, simulate, executable-address — ALLOW/DENY/ESCALATE |
| Exact approvals | ✅ Real | PREFILL-07 compliant, never max-uint |
| Sponsored execution | ✅ Real | Supply + withdraw sponsored on Sepolia (`"sponsored": true`) |
| Onchain verification | ✅ Real | aWETH `balanceOf` read-back, arithmetic verified (0.005 − 0.002 = 0.003) |
| Zero-tx DENY | ✅ Real | Out-of-policy AND rank-only venues: nothing broadcast |
| Audit trail | ✅ Real | Every decision JSONL-logged with checks + outcome |
| Human-in-the-loop | ✅ Real | `list_escalations` / `resolve_escalation` (MCP + CLI) |
| Scheduled deposits | ✅ Real | `scripts/plow_scheduler.py` — scan → rank → gate → deposit loop |
| Venue | ✅ Real | Aave V3 (deployed protocol); asset = Aave's Sepolia WETH mock (standard testnet asset) |
| Multi-chain | ✅ Engine live | Chain-abstracted (Base Sepolia 84532 policy, RPC override, `--chain`); Base demo deposit pending testnet bridge relay |
| Mainnet venues | 🟡 Config-gated | Aave V3 mainnet + Sky/Ethena adapters in `policies.mainnet.example.json` — audit before use |
| External audit | ⚠️ Not done | Do not use with real funds |

---

## Tests

**21 tests passing** (38 checks), all green:

```
=== Python (server) ===
All tests passed — 21/21
gate: unlisted DENY, disabled DENY, rank-only (no executable address) DENY,
zero-amount DENY, cap DENY, simulate-revert DENY, fail-closed DENY, in-policy
ALLOW, over-budget ESCALATE, active-window wraparound, intent-key determinism,
BYOK precedence, calldata selectors, rank excludes unmatched venues, rank fails
loudly on feed failure, rank live-APY match, escalation lifecycle (list/reject),
scheduler addressable-venue selection, verify unknown venue, scan empty,
status poll retries empty hash (B8)
```

Run them:

```bash
.venv/bin/python server/test_plow.py   # 21 tests
```

---

## Run it locally

**Prerequisites:** Python 3.12+, a KeeperHub org API key
(`kh_...` from app.keeperhub.com → Settings → API Keys).

```bash
git clone https://github.com/subheeksh5599/plow.git
cd plow

uv venv .venv
uv pip install --python .venv/bin/python -r server/requirements.txt
cp .env.example .env                # fill KH_API_KEY
.venv/bin/python server/test_plow.py

# CLI demo (Sepolia, org wallet)
.venv/bin/python scripts/plow_cli.py scan --address 0x1776D4D751d97c85845bF54e6CE364CEc62D4bBf
.venv/bin/python scripts/plow_cli.py rank
.venv/bin/python scripts/plow_cli.py deposit --venue aave-v3-weth --amount 0.005

# Frontend
cd frontend && npm install && npm run build   # static export → out/
```

Point `PLOW_POLICY_PATH` at `server/policies.json` (venues + tokens config) and
`KEEPERHUB_CHAIN_ID` at your chain (11155111 = Sepolia, 84532 = Base Sepolia).

### policies.json reference

```jsonc
{
  "window": { "start": 0, "end": 23 },              // UTC hours; 23→5 wraps overnight
  "functionAllowlist": ["approve(address,uint256)", "supply(address,uint256,address,uint16)", "withdraw(address,uint256,address)"],
  "tokens": [ { "symbol": "WETH", "address": "0x…", "decimals": 18 } ],
  "venues": [
    {
      "id": "aave-v3-weth",
      "name": "Aave V3 (WETH supply)",
      "address": "0x…",                             // Aave V3 Pool
      "tokenAddress": "0x…",                        // the asset to supply
      "aTokenAddress": "0x…",                       // where positions are verified
      "functionName": "supply",                     // gate's function-allowlist key
      "enabled": true,
      "maxDeposit": 0.02,                           // per-deposit cap
      "budget": 0.05,                               // per-period budget
      "budgetPeriodHours": 24,
      "defillamaProject": "aave-v3",                // live-APY hint
      "defillamaSymbol": "WETH"
    }
  ]
}
```

A venue with a zero `address` is **rank-only**: it appears in APY context but
the gate DENYs any deposit to it (zero transactions broadcast).

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `kh_api_key_not_set` | `KH_API_KEY` missing — set it in `.env` or export it |
| `DENY ... simulation unavailable (fail closed)` | KeeperHub simulate call failed; `PLOW_FAIL_CLOSED=0` disables the hard stop (not recommended) |
| `DENY ... approve simulation reverted` | The token's approve is blocked for this spender/amount |
| `DENY ... venue has no executable address` | The venue is rank-only (zero address) — pick an addressable one |
| 502 on contract-call | Transient KeeperHub upstream — the client retries 3× with backoff |
| `DENY ... over per-period budget` | Check `budget` / `budgetPeriodHours`; raise it or wait for the period to roll |
| `rank_venues` errors | The DefiLlama feed is unreachable — by design Plow fails loudly instead of faking rates |

---

## Deploy

| | |
|---|---|
| **Frontend** | **[plow-beta.vercel.app](https://plow-beta.vercel.app)** — Vercel static export |
| **Server** | Vercel serverless function (`api/index.py` → ASGI `server.plow.app`), `KH_API_KEY` in env |
| **Venue** | Aave V3 Pool on Sepolia (real protocol, no custom contracts) |

The frontend is a static export (Next.js 16, `output: export`). The Plow API
exposes `POST /api/plow` (MCP-shaped JSON-RPC) and `GET /api/health` behind the
same alias, with bring-your-own-key: a per-request `Authorization: Bearer
kh_...` header wins over the env key.

---

## Project layout

```
plow/
├── server/                # Python agent core
│   ├── plow.py            # KeeperHub client, BYOK, policy gate, scan/rank,
│   │                      #   supply/withdraw, escalation, MCP tools, ASGI app
│   ├── policies.json      # Sepolia venue allowlist, caps, budgets, window
│   ├── policies.base.json # Base Sepolia policy (config-ready)
│   ├── policies.mainnet.example.json  # mainnet adapters, disabled
│   └── test_plow.py       # 22 unit tests (plain asserts)
├── scripts/
│   ├── plow_cli.py        # terminal demo (scan/rank/deposit/verify/escalations)
│   ├── run_demos.py       # live demo runs → evidence-<chain>.json
│   ├── make_graphs.py     # README graphs from run data
│   ├── make_demo_video.py # demo video renderer (PIL + ffmpeg)
│   ├── plow_scheduler.py  # recurring yield placement loop
│   └── smoke_test.py      # deployed-API smoke test
├── frontend/              # Next.js 16 static export landing
├── docs/media/            # README screenshots + graphs
├── docs/demo/             # demo video + narration assets
├── audits/                # plow-audit.jsonl (local)
├── api/                   # Vercel serverless entrypoint
├── .github/               # CI workflow, dependabot, PR template
├── evidence-<chain>.json  # latest demo run evidence (local)
├── Makefile               # test/build/verify targets
├── SECURITY.md · CONTRIBUTING.md · .env.example
└── README.md
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Agent core | Python 3.12, httpx (async) |
| Execution | KeeperHub direct-execution API (sponsored contract-calls) |
| Venue | Aave V3 (Sepolia Pool) — supply / withdraw, aToken verification |
| Yields | DefiLlama yields API (live, cache, no fallback) |
| Chain reads | JSON-RPC `eth_call` (publicnode, override via env) |
| Frontend | Next.js 16, React 19, static export |
| MCP surface | JSON-RPC over HTTP, BYOK per request |
| Chain | Ethereum Sepolia (11155111) |

---

## Roadmap

- **✅ Real venue** — Aave V3 (WETH supply) on Sepolia: supply + withdraw
  executed gas-sponsored through KeeperHub, verified onchain.
- **✅ Live APY** — DefiLlama Aave V3 WETH pool (1.43% at the time of writing),
  no fallback, TVL surfaced.
- **✅ Scheduled deposits** — `scripts/plow_scheduler.py`: recurring scan → rank →
  gate → deposit loop with policy budgets.
- **✅ Escalation loop** — `list_escalations` / `resolve_escalation` MCP tools +
  CLI: over-budget proposals pause for a human, approve re-runs the gated supply.
- **✅ Multi-chain engine** — chain-abstracted execution (chainId 84532 policy,
  RPC override, `--chain` flag). The Base Sepolia demo deposit is configured and
  ready; it waits on a working testnet bridge relay.
- **🟡 Mainnet execution** — flip `KEEPERHUB_CHAIN_ID` + real venue addresses
  (Aave V3 mainnet, Sky, Ethena — configs in `policies.mainnet.example.json`);
  requires the external audit first. Never run with real funds today.

---

## License

MIT — built for the KeeperHub Agents Onchain Hackathon.
