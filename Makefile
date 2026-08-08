# Plow — developer convenience targets.
#  make test        run the python suite
#  make build       build the frontend static export
#  make verify      smoke-test the deployed API (needs KH_API_KEY + URL)

.PHONY: test build verify clean

test:
	.venv/bin/python server/test_plow.py

build:
	cd frontend && npm run build

verify:
	.venv/bin/python scripts/smoke_test.py

clean:
	rm -rf frontend/out frontend/.next
