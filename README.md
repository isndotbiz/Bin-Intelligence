# BIN Intelligence System

BIN intelligence platform for e-commerce fraud analysis, enrichment, and reporting.

## Investor Summary
Fraud prevention teams need reliable BIN intelligence to evaluate card risk and 3DS posture. This platform automates BIN ingestion, enrichment, classification, and reporting with a dashboard and API, enabling faster decisions and easier integration into fraud workflows.

## Product Scope and Capabilities
- Flask dashboard and REST API for BIN analytics.
- Automated BIN enrichment using Neutrino API.
- Fraud feed scraping and exploit classification.
- SQLAlchemy storage with export and reporting utilities.

## Differentiation and Moat
- Automated enrichment and exploit classification in a single system.
- Clear API surface plus operator dashboard.
- Extensible data model for new exploit types.

## Evidence of Execution
- End-to-end pipeline in `main.py` with API endpoints.
- Data model and enrichment in `models.py` and `bin_enricher.py`.
- Deployment and operational docs in `DEPLOYMENT.md` and `API.md`.

## Technology Stack
- Python 3.11, Flask, SQLAlchemy
- PostgreSQL or SQLite
- Neutrino BIN Lookup API
- Bootstrap and Chart.js UI

## Commercial Use Cases
- Fraud prevention and risk teams at e-commerce platforms.
- Payment processors and merchant service providers.
- Security analytics teams needing BIN-based threat insights.

## Repository Map
```
main.py             Flask app and API
models.py           SQLAlchemy schema
bin_enricher.py     Enrichment pipeline
fraud_feed.py       Scrapers
templates/          Dashboard UI
```

## Quick Start
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="sqlite:///bin_intelligence.db"
export NEUTRINO_API_USER_ID="your_user_id"
export NEUTRINO_API_KEY="your_api_key"

python main.py
```

## License
See LICENSE in the repo.
