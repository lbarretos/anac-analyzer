.PHONY: setup etl etl-full test dev build

setup:
	pip install -r requirements-dev.txt
	cd app && npm install

# Carga incremental (uso recorrente)
etl:
	cd etl && python run_all.py

# Carga completa desde 2010 (primeira vez)
etl-full:
	cd etl && python run_all.py --full

test:
	pytest tests/ -v

dev:
	cd app && npm run dev

build:
	cd app && npm run build
