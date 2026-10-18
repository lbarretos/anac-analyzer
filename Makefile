.PHONY: setup etl etl-full test check eval mcp dev build

setup:
	./setup.sh

check:
	.venv/bin/python scripts/check_integrity.py

eval:
	.venv/bin/python scripts/eval/eval_llm.py

mcp:
	.venv/bin/python scripts/mcp/anac_mcp.py

test:
	.venv/bin/pytest tests/ -v

etl:
	.venv/bin/python etl/run_all.py

etl-full:
	.venv/bin/python etl/run_all.py --full

dev:
	cd app && bun run dev || npm run dev

build:
	cd app && bun run build || npm run build
