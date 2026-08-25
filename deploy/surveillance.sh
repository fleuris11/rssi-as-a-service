#!/usr/bin/env bash
# Surveillance interne de la production.
#
# Complète la surveillance EXTERNE (UptimeRobot, voir
# docs/deploiement_production.md §Supervision) sans la remplacer : celle-ci
# voit ce que l'extérieur ne peut pas voir — un conteneur redémarré en boucle,
# un worker Celery muet, un disque qui se remplit — mais elle ne verra jamais
# une panne du serveur lui-même, puisqu'elle tourne dessus. Les deux sont
# nécessaires, aucune ne suffit.
#
# Règle anti-faux positif reprise du produit (CLAUDE.md) : on alerte après
# TROIS échecs consécutifs, pas au premier. Un redémarrage de conteneur ou un
# pic de charge ne doit pas réveiller l'exploitant.
set -uo pipefail

PROJET="${PROJET:-$HOME/rssi}"
ETAT="${ETAT:-$HOME/.surveillance-etat}"
SEUIL="${SEUIL:-3}"
COMPOSE="docker compose -f $PROJET/docker-compose.prod.yml"

mkdir -p "$ETAT"

problemes=()

# --- Les services tournent-ils ? --------------------------------------------
for service in postgres redis web worker beat caddy; do
    statut=$($COMPOSE ps -a --format '{{.Service}} {{.State}}' 2>/dev/null \
             | awk -v s="$service" '$1==s {print $2}' | head -1)
    [ "$statut" = "running" ] || problemes+=("service $service : ${statut:-absent}")
done

# --- Le site répond-il, vu de la machine ? ----------------------------------
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://rssiasservice.online/healthz || echo 000)
[ "$code" = "200" ] || problemes+=("https://rssiasservice.online/healthz : HTTP $code")

# --- Un worker Celery répond-il ? -------------------------------------------
# Un worker « running » pour Docker peut être bloqué : on lui parle.
if ! $COMPOSE exec -T web python -c "
from config.celery import app
import sys
sys.exit(0 if (app.control.inspect(timeout=8).ping() or {}) else 1)
" >/dev/null 2>&1; then
    problemes+=("aucun worker Celery ne répond")
fi

# --- Le disque a-t-il de la place ? -----------------------------------------
# Un disque plein casse PostgreSQL de façon spectaculaire et tardive.
occupation=$(df --output=pcent / | tail -1 | tr -dc '0-9')
[ "${occupation:-0}" -ge 85 ] && problemes+=("disque occupé à ${occupation} %")

# --- Le certificat expire-t-il bientôt ? ------------------------------------
fin=$(echo | timeout 15 openssl s_client -connect rssiasservice.online:443 \
      -servername rssiasservice.online 2>/dev/null \
      | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
if [ -n "$fin" ]; then
    restant=$(( ( $(date -d "$fin" +%s) - $(date +%s) ) / 86400 ))
    [ "$restant" -lt 10 ] && problemes+=("certificat TLS : expire dans $restant jour(s)")
fi

# --- Décision ---------------------------------------------------------------
compteur_fichier="$ETAT/echecs"
alerte_fichier="$ETAT/alerte-envoyee"

if [ ${#problemes[@]} -eq 0 ]; then
    # Retour à la normale : on prévient si une alerte avait été envoyée.
    if [ -f "$alerte_fichier" ]; then
        "$PROJET/deploy/surveillance-envoi.sh" "Retour à la normale" \
            "Tous les contrôles repassent au vert." || true
        rm -f "$alerte_fichier"
    fi
    echo 0 > "$compteur_fichier"
    echo "$(date -Iseconds) OK"
    exit 0
fi

echecs=$(( $(cat "$compteur_fichier" 2>/dev/null || echo 0) + 1 ))
echo "$echecs" > "$compteur_fichier"

resume=$(printf '  - %s\n' "${problemes[@]}")
echo "$(date -Iseconds) ECHEC ($echecs/$SEUIL)"
echo "$resume"

# Alerte au seuil, puis plus rien tant que l'incident dure : une alerte
# répétée toutes les cinq minutes cesse d'être lue.
if [ "$echecs" -ge "$SEUIL" ] && [ ! -f "$alerte_fichier" ]; then
    "$PROJET/deploy/surveillance-envoi.sh" \
        "Incident sur rssiasservice.online" \
        "$echecs contrôles consécutifs en échec :

$resume

Serveur : $(hostname) — $(date -Iseconds)" && touch "$alerte_fichier"
fi
exit 1
