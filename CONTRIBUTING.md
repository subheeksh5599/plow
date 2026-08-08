# Contributing to Plow

Thanks for taking a look. Plow is a hackathon build, but the door is open for
real improvements — especially anything that makes the write path safer.

## Scope

- **Testnet-only**: any change must keep Plow safe for testnets and clearly
  gated for mainnet (config-gated, `enabled: false`, audit required).
- **No real funds**: never merge something that could touch real funds without
  an explicit, documented audit gate.

## Getting started

```bash
git clone https://github.com/subheeksh5599/plow.git
cd plow
uv venv .venv
uv pip install --python .venv/bin/python -r server/requirements.txt
KH_API_KEY=kh_test_key .venv/bin/python server/test_plow.py   # unit tests, no network
cd contracts && forge test                                    # solidity tests
```

Frontend: `cd frontend && npm install && npm run build`.

## What to work on

- **Reliability**: retries, idempotency, gas handling, audit completeness
- **Policy engine**: more gate checks, clearer ALLOW/DENY/ESCALATE semantics
- **Onboarding**: the fastest path from zero to a first executed transaction
- **Docs and tests**: anything that makes the repo easier to judge

## Pull requests

- Small, focused PRs with a clear title and a short description
- Run the tests before pushing: `make test`
- Keep the honesty table in the README honest — update it if behavior changes
- No `max-uint` approvals, ever (PREFILL-07)

## Commit style

Conventional prefixes (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`),
small logical commits. See the repo history for the pattern.

## Security

See [SECURITY.md](SECURITY.md). Findings go to a private advisory, not issues.
