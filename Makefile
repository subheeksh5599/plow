# Plow — developer convenience targets.
#  make test        run forge + python suites
#  make build       build the frontend static export
#  make verify      smoke-test the deployed API (needs KH_API_KEY + URL)

.PHONY: test build verify clean

test:
	cd contracts && forge test
	.venv/bin/python server/test_plow.py

build:
	cd frontend && npm run build

verify:
	.venv/bin/python scripts/smoke_test.py

clean:
	rm -rf frontend/out frontend/.next contracts/out contracts/cache
