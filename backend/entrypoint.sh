#!/bin/sh
set -e

python - <<'PYEOF'
import os
import sys
import time

import psycopg

url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
deadline = time.time() + 30

while True:
    try:
        with psycopg.connect(url, connect_timeout=3):
            break
    except psycopg.OperationalError:
        if time.time() > deadline:
            print("Base de données indisponible après 30s, abandon.", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)
PYEOF

python manage.py migrate --noinput

exec "$@"
