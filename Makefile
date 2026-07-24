.PHONY: install ingest ingest-public-validation transform export-deploy-db build-ui app dev test evaluate check-meta-token clean

PYTHON ?= .venv/bin/python

install:
	uv venv --python 3.11 .venv
	uv pip install --python $(PYTHON) -r requirements-dev.txt
	npm install

ingest:
	$(PYTHON) -m src.ingest.fetch_ftc
	$(PYTHON) -m src.ingest.fetch_cfpb
	$(PYTHON) -m src.ingest.fetch_meta_ads
	$(PYTHON) -m src.ingest.fetch_tiktok_commercial_ads

ingest-public-validation:
	$(PYTHON) -m src.ingest.fetch_uw_bad_ads

transform:
	$(PYTHON) -m src.transform.normalize_ftc
	$(PYTHON) -m src.transform.normalize_cfpb
	$(PYTHON) -m src.transform.normalize_ads
	$(PYTHON) -m src.transform.build_duckdb

export-deploy-db:
	$(PYTHON) -m scripts.export_deploy_db

build-ui:
	npm run build

app: build-ui
	$(PYTHON) -m src.app.api

dev:
	$(PYTHON) scripts/run_dev.py

test:
	$(PYTHON) -m pytest -q
	npm run build

evaluate:
	$(PYTHON) -m src.analytics.evaluate

check-meta-token:
	$(PYTHON) scripts/check_meta_token.py

clean:
	rm -rf dist .pytest_cache
