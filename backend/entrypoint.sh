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

# Les migrations NE sont PLUS appliquees ici.
#
# web, worker et beat partagent cet entrypoint : ils les executaient donc tous
# les trois en parallele, se disputant la creation des memes tables. Le
# perdant s'arretait sur « duplicate key value violates unique constraint
# pg_type_typname_nsp_index ». Une course, donc intermittente, et d'autant
# plus deroutante que le service survivant faisait croire a un demarrage
# reussi.
#
# Un service « migrate » dedie les applique une seule fois ; les autres
# attendent qu'il ait termine (depends_on: service_completed_successfully).
exec "$@"
