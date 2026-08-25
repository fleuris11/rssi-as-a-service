#!/usr/bin/env bash
# Renseigne un secret dans backend/.env sans qu'il transite par un argument
# de ligne de commande.
#
# Pourquoi pas un simple `sed -i "s/CLE=/CLE=sk-ant-.../"` : un argument de
# commande est visible dans `ps` par tout utilisateur de la machine, et reste
# dans l'historique du shell. La saisie masquée (`read -s`) évite les deux.
#
# Usage : ./deploy/configurer-secret.sh NOM_DE_LA_VARIABLE
set -euo pipefail

ENV_FILE="${ENV_FILE:-$HOME/rssi/backend/.env}"
VAR="${1:-}"

if [ -z "$VAR" ]; then
    echo "Usage : $0 NOM_DE_LA_VARIABLE" >&2
    echo "Exemple : $0 ANTHROPIC_API_KEY" >&2
    exit 1
fi
if ! grep -q "^${VAR}=" "$ENV_FILE"; then
    echo "Variable inconnue dans $ENV_FILE : $VAR" >&2
    echo "Variables disponibles :" >&2
    grep -oE '^[A-Z_]+=' "$ENV_FILE" | tr -d '=' | sed 's/^/  /' >&2
    exit 1
fi

printf 'Valeur pour %s (rien ne s affiche pendant la frappe) : ' "$VAR"
read -rs valeur
echo

if [ -z "$valeur" ]; then
    echo "Valeur vide : aucune modification." >&2
    exit 1
fi

# Sauvegarde avant modification : une erreur sur .env casse tout le service.
cp "$ENV_FILE" "$ENV_FILE.avant-$(date +%s)"

# python plutôt que sed : la valeur peut contenir /, &, \ — autant de
# caractères que sed interpréterait.
VALEUR="$valeur" VAR="$VAR" python3 - "$ENV_FILE" <<'PY'
import os, sys
chemin, var, valeur = sys.argv[1], os.environ["VAR"], os.environ["VALEUR"]
lignes = open(chemin, encoding="utf-8").read().splitlines()
sortie = [f"{var}={valeur}" if l.startswith(f"{var}=") else l for l in lignes]
open(chemin, "w", encoding="utf-8").write("\n".join(sortie) + "\n")
PY

chmod 600 "$ENV_FILE"
longueur=${#valeur}
echo "$VAR renseignée ($longueur caractères). Valeur jamais affichée."
echo "Redémarrez les services pour l'appliquer :"
echo "  cd ~/rssi && docker compose -f docker-compose.prod.yml up -d"
