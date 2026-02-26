# Bin-Intelligence

BIN intelligence platform for e-commerce fraud analysis, enrichment, and reporting.

## Stack

- Python 3.11, Flask, SQLAlchemy
- PostgreSQL or SQLite
- Neutrino BIN Lookup API

## Key Files

- `main.py` - Flask app and REST API endpoints
- `models.py` - SQLAlchemy schema
- `bin_enricher.py` - Enrichment pipeline (Neutrino API)
- `fraud_feed.py` - Fraud feed scrapers and exploit classification
- `templates/` - Dashboard UI (Bootstrap + Chart.js)

## Dev Notes

- Install deps: `pip install -r requirements.txt` or `uv sync`
- Run locally: `python main.py`
- API docs: see `API.md`
- Deployment: see `DEPLOYMENT.md`
