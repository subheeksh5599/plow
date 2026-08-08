# Security Policy

## Supported environments

Plow is a **testnet-only** project today. It executes on Ethereum Sepolia and
Base Sepolia, against mock venue contracts, with gas sponsored by KeeperHub.

## ⚠️ No real funds

- Plow has **not** been externally audited.
- **Do not use Plow with real funds.**
- The mainnet venue adapters in `server/policies.mainnet.example.json` are
  config-gated and **disabled** by default (`"enabled": false`).

## Reporting a vulnerability

Please do **not** open a public issue for security findings.

- Report privately via a GitHub security advisory
  (Repo → Security → Report a vulnerability), or
- Email the maintainer through the address on the GitHub profile.

Please include:

- A description of the issue and its impact
- Steps to reproduce (chain, venue, policy, tx if any)
- Suggested fix, if you have one

## Guardrails built in

- **Fail closed**: unavailable simulation → `DENY`
- **Exact approvals only** (PREFILL-07): never `max-uint`
- **Zero-tx DENY**: out-of-policy and rank-only venues broadcast nothing
- **Allowlist-only execution**: deposits only to configured venue addresses
- **BYOK**: per-request API keys; env key is the fallback, never in the bundle
