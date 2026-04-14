# Bin-Intelligence v2.3.0

BIN intelligence platform for e-commerce fraud analysis — classifies BINs by 3D Secure posture, issuer, and exploit type.

## Stack
- Python 3.11, Flask 3.1.1, SQLAlchemy 2.0.41
- PostgreSQL (prod) or SQLite (dev)
- Neutrino BIN Lookup API, Adyen BinLookup API
- Bootstrap + Chart.js dashboard (dark theme), gunicorn

## Key Files
- `main.py` — Flask app, DB engine/session, all endpoints
- `models.py` — SQLAlchemy: `BIN`, `ExploitType`, `BINExploit`, `ScanHistory`
- `bin_enricher.py` — Adyen 3DS data, Neutrino metadata, heuristic fallback
- `neutrino_api.py` — `NeutrinoAPIClient` (User-ID/API-Key headers)
- `adyen_client.py` — `AdyenBinLookupClient` (`get3dsAvailability`)
- `fraud_feed.py` — `FraudFeedScraper`: scrapes feeds, classifies exploits
- `templates/dashboard.html` — primary UI (ignore `.bak`/`.old` files)

## Dev Commands
```bash
pip install -r requirements.txt   # or: uv sync
python main.py                    # runs on port 5000
```

## Environment Variables
```bash
DATABASE_URL="postgresql://..."   # REQUIRED — auto-rewrites postgres:// prefix
NEUTRINO_API_USER_ID="..."        # required for enrichment
NEUTRINO_API_KEY="..."            # required for enrichment
ADYEN_API_KEY="..."               # optional: real 3DS enrollment
ADYEN_MERCHANT_ACCOUNT="..."      # optional: with ADYEN_API_KEY
ADYEN_USE_TEST="true"             # default: true
```

## Domain Concepts
- **Exploit types:** `card-not-present`, `cvv-weak`, `no-auto-3ds`
- **patch_status:** `Patched` (≥1 3DS version supported) vs `Exploitable` (no 3DS)
- Migration scripts in repo root (`add_card_level_column.py`, `migrate_database.py`, etc.)

## Credentials
All credentials via 1Password Connect (global env `OP_CONNECT_HOST`/`OP_CONNECT_TOKEN`).
- `op read "op://Research/Neutrino API/password"` etc.
- See global CLAUDE.md for Connect host/token.
