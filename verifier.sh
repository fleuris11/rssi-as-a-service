#!/usr/bin/env bash
# Vérification locale — reproduit EXACTEMENT ce que la CI contrôle.
#
# Raison d'être : la CI est restée rouge deux semaines parce que la
# vérification locale documentée ne couvrait pas tout ce qu'elle vérifie. En
# particulier `ruff format .` (qui APPLIQUE le format) au lieu de
# `ruff format --check .` (qui ÉCHOUE s'il n'est pas appliqué) : on pouvait
# croire avoir vérifié sans l'avoir fait.
#
# Toute étape ajoutée à .github/workflows/ci.yml doit l'être ici aussi.
#
# Usage :
#   ./verifier.sh          tout
#   ./verifier.sh back     backend seulement
#   ./verifier.sh front    frontend seulement
#
# Note : les trois tests d'export PDF (WeasyPrint) échouent sous Windows faute
# de Pango/Cairo, et passent en conteneur comme en CI. C'est le seul écart
# connu entre ce script et le résultat de la CI.
set -uo pipefail

RACINE="$(cd "$(dirname "$0")" && pwd)"
PORTEE="${1:-tout}"
ECHECS=()

# Le venv du backend s'il existe, sinon le python du PATH.
PY="python"
[ -x "$RACINE/backend/venv/Scripts/python.exe" ] && PY="$RACINE/backend/venv/Scripts/python.exe"
[ -x "$RACINE/backend/venv/bin/python" ] && PY="$RACINE/backend/venv/bin/python"

etape() {
    local nom="$1"; shift
    printf '\n\033[1m▸ %s\033[0m\n' "$nom"
    if "$@"; then
        printf '\033[32m  ✓ %s\033[0m\n' "$nom"
    else
        printf '\033[31m  ✗ %s\033[0m\n' "$nom"
        ECHECS+=("$nom")
    fi
}

# Fins de ligne des scripts : un fichier en CRLF est inexécutable sous Linux
# (« /usr/bin/env: 'bash^M': No such file or directory », ou « set: Illegal
# option - »), messages qui ne désignent pas la cause. Le .gitattributes
# normalise à la validation, mais une image Docker construite depuis l'arbre
# de travail lit le fichier tel quel : l'erreur n'apparaît qu'au démarrage du
# conteneur, souvent en intégration continue.
#
# La détection compare le fichier à lui-même privé de ses retours chariot. Ni
# grep ni awk ne conviennent : le motif dépend de leur implémentation, et
# l'awk de Git Bash y voit la lettre « r », signalant donc tout fichier
# contenant cette lettre. Un contrôle qui ne contrôle rien est pire qu'aucun.
verifier_fins_de_ligne() {
    local fautifs=""
    local retour_chariot
    retour_chariot=$(printf '\015')
    while IFS= read -r f; do
        if ! tr -d "$retour_chariot" < "$f" | cmp -s - "$f"; then
            fautifs="$fautifs    $f"$'\n'
        fi
    done < <(find "$RACINE" -name '*.sh' -not -path '*/node_modules/*' -not -path '*/venv/*')
    [ -z "$fautifs" ] && return 0
    echo "Scripts avec des fins de ligne Windows (CRLF) :" >&2
    printf '%s' "$fautifs" >&2
    return 1
}

etape "fins de ligne des scripts" verifier_fins_de_ligne

if [ "$PORTEE" = "tout" ] || [ "$PORTEE" = "back" ]; then
    cd "$RACINE/backend"
    etape "ruff check"            "$PY" -m ruff check .
    # --check et non l'application : c'est ce que fait la CI.
    etape "ruff format --check"   "$PY" -m ruff format --check .
    etape "migrations manquantes" "$PY" manage.py makemigrations --check --dry-run
    etape "pytest"                "$PY" -m pytest -q
    etape "pip-audit"             "$PY" -m pip_audit -r requirements.txt --strict
fi

if [ "$PORTEE" = "tout" ] || [ "$PORTEE" = "front" ]; then
    cd "$RACINE/frontend"
    etape "eslint"       npm run lint
    etape "build"        npm run build
    etape "npm audit"    npm run audit
    etape "vitest"       npm test
fi

printf '\n'
if [ ${#ECHECS[@]} -eq 0 ]; then
    printf '\033[32m✓ Tout est vert — la CI devrait passer.\033[0m\n'
    exit 0
fi
printf '\033[31m✗ %d étape(s) en échec :\033[0m\n' "${#ECHECS[@]}"
printf '    %s\n' "${ECHECS[@]}"
printf '\nLa CI échouera. Ne pas fusionner en l%stat (CLAUDE.md).\n' "'é"
exit 1
