#!/usr/bin/env bash
# Sauvegarde quotidienne de la production.
#
# Sauvegarde DEUX choses, et c'est délibéré :
#
#   1. la base PostgreSQL ;
#   2. le fichier backend/.env, qui porte les CLÉS DE CHIFFREMENT.
#
# Sans le second, le premier est en partie inutilisable : les mots de passe
# fuités sont chiffrés en base (ADR-014), et une restauration sans la clé
# rendrait ces données définitivement illisibles. C'est l'oubli classique,
# constaté seulement le jour où l'on restaure.
#
# L'archive contient donc des secrets : permissions 600, et elle ne doit
# jamais être déposée sur un stockage tiers en clair.
set -euo pipefail

PROJET="${PROJET:-$HOME/rssi}"
DESTINATION="${DESTINATION:-$HOME/sauvegardes}"
RETENTION_JOURS="${RETENTION_JOURS:-14}"
COMPOSE="docker compose -f $PROJET/docker-compose.prod.yml"

horodatage=$(date +%Y-%m-%d_%Hh%M)
travail=$(mktemp -d)
trap 'rm -rf "$travail"' EXIT

mkdir -p "$DESTINATION"
chmod 700 "$DESTINATION"

# --- Base de données --------------------------------------------------------
# --clean --if-exists : le fichier restaure sur une base existante sans exiger
# de la recréer à la main.
cd "$PROJET"
$COMPOSE exec -T postgres pg_dump \
    -U "${POSTGRES_USER:-rssiasservice}" \
    -d "${POSTGRES_DB:-rssiasservice}" \
    --clean --if-exists > "$travail/base.sql"

lignes=$(wc -l < "$travail/base.sql")
if [ "$lignes" -lt 50 ]; then
    echo "ABANDON : le dump ne fait que $lignes lignes, il est probablement vide." >&2
    exit 1
fi

# --- Secrets ----------------------------------------------------------------
cp "$PROJET/backend/.env" "$travail/env"

# --- Repère de version ------------------------------------------------------
# Savoir QUEL code tournait quand la sauvegarde a été prise : restaurer une
# base sur une version d'application plus ancienne casse les migrations.
git -C "$PROJET" log --oneline -1 > "$travail/commit.txt" 2>/dev/null || true
date -Iseconds > "$travail/date.txt"

archive="$DESTINATION/rssi_$horodatage.tar.gz"
tar czf "$archive" -C "$travail" base.sql env commit.txt date.txt
chmod 600 "$archive"

# --- Rotation ---------------------------------------------------------------
find "$DESTINATION" -name 'rssi_*.tar.gz' -mtime +"$RETENTION_JOURS" -delete

taille=$(du -h "$archive" | cut -f1)
echo "$(date -Iseconds) OK $archive ($taille, $lignes lignes SQL)"
