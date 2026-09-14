#!/usr/bin/env sh
set -e

echo "[libraflow] applying schema migrations..."
alembic upgrade head

echo "[libraflow] seeding catalog, branches and default admin..."
python scripts/seed_data.py

echo "[libraflow] starting uvicorn on 0.0.0.0:8000"
exec python -m uvicorn libflow.api.app:app --host 0.0.0.0 --port 8000