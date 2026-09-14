#!/usr/bin/env sh
set -e

echo "[libraflow] applying schema migrations..."
alembic upgrade head
echo "[libraflow] migration finished."