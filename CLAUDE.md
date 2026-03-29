# Bin-Intelligence

## 1Password Connect — Credential Access
All credentials via 1Password Connect. No service accounts, no desktop auth, no plaintext .env secrets.
- `OP_CONNECT_HOST=http://100.67.89.29:8100`
- `OP_CONNECT_TOKEN` — set in global CLAUDE.md (inherited automatically)
- Vaults: `Research`, `TrueNAS Infrastructure`
- Usage: `op item get "Name" --vault "Research" --format json`

BIN intelligence platform for e-commerce fraud analysis, enrichment, and reporting. A BIN (Bank Identification Number) is the first 6 digits of a payment card; this system classifies BINs by 3D Secure posture, issuer, and exploit type.

Current version: **2.3.0**

## Stack

- Python 3.11, Flask 3.1.1, SQLAlchemy 2.0.41
- PostgreSQL (production) or SQLite (development)
- Neutrino BIN Lookup API (`https://neutrinoapi.net/bin-lookup/`)
- Bootstrap + Chart.js dashboard (dark theme)
- gunicorn for production serving

## Required Environment Variables

```bash
DATABASE_URL="postgresql://user:pass@host:5432/dbname"  # Required on startup
NEUTRINO_API_USER_ID="your_user_id"                     # Required for enrichment
NEUTRINO_API_KEY="your_api_key"                         # Required for enrichment
ADYEN_API_KEY="your_adyen_key"                          # Optional: real 3DS enrollment data
ADYEN_MERCHANT_ACCOUNT="your_merchant"                  # Optional: required with ADYEN_API_KEY
ADYEN_USE_TEST="true"                                   # Optional: use Adyen test environment (default: true)
```

`DATABASE_URL` starting with `postgres://` is auto-rewritten to `postgresql://` at startup. App raises `ValueError` and refuses to start if `DATABASE_URL` is unset.

## Key Files

- `main.py` - Flask app, DB engine/session setup, all API and web endpoints
- `models.py` - SQLAlchemy models: `BIN`, `ExploitType`, `BINExploit`, `ScanHistory`
- `bin_enricher.py` - `BinEnricher` class: uses Adyen BinLookup for real 3DS data, Neutrino for metadata, heuristic fallback
- `neutrino_api.py` - `NeutrinoAPIClient`: authenticates via `User-ID`/`API-Key` headers (supplementary metadata)
- `adyen_client.py` - `AdyenBinLookupClient`: queries Adyen `get3dsAvailability` for real 3DS enrollment data
- `fraud_feed.py` - `FraudFeedScraper`: scrapes public feeds, extracts PANs, classifies exploits
- `utils.py` - CSV/JSON export helpers
- `templates/dashboard.html` - Primary dashboard UI

## Exploit Types (3 total)

- `card-not-present` - BINs used in CNP/online fraud
- `cvv-weak` - BINs where CVV verification is weak (issuer returns response code U or P)
- `no-auto-3ds` - BINs lacking automatic 3DS frictionless flow

## patch_status Values

- `Patched` - at least one of `threeds1_supported` or `threeds2_supported` is true
- `Exploitable` - neither 3DS version supported (Adyen lookup or heuristic inference)

## Dev Notes

- Install deps: `pip install -r requirements.txt` or `uv sync`
- Run locally: `python main.py` (listens on port 5000)
- API docs: see `API.md`
- Deployment guide: see `DEPLOYMENT.md`
- One-off DB migration scripts are in the repo root (`add_card_level_column.py`, `migrate_database.py`, etc.)
- `templates/` contains backup files (`.bak`, `.old`) alongside production `dashboard.html` — use `dashboard.html`
