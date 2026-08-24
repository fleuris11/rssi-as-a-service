#!/usr/bin/env bash
# Configure l'envoi d'emails et le VÉRIFIE par un envoi réel.
#
# Une configuration SMTP acceptée n'est pas une configuration qui fonctionne :
# l'authentification peut passer et l'envoi être refusé, ou l'email partir et
# n'arriver nulle part. Ce script envoie donc un message de test et rapporte
# ce que le serveur a réellement répondu.
set -euo pipefail

PROJET="${PROJET:-$HOME/rssi}"
ENV_FILE="$PROJET/backend/.env"
COMPOSE="docker compose -f $PROJET/docker-compose.prod.yml"

echo "Configuration de l'envoi d'emails"
echo "---------------------------------"
printf 'Adresse email complete (ex: contact@rssiasservice.online) : '
read -r adresse
[ -z "$adresse" ] && { echo "Adresse vide, abandon." >&2; exit 1; }

printf 'Mot de passe de cette boite (rien ne s affiche) : '
read -rs motdepasse
echo
[ -z "$motdepasse" ] && { echo "Mot de passe vide, abandon." >&2; exit 1; }

cp "$ENV_FILE" "$ENV_FILE.avant-email"

ADRESSE="$adresse" MOTDEPASSE="$motdepasse" python3 - "$ENV_FILE" <<'PY'
import os, sys
chemin = sys.argv[1]
adresse, motdepasse = os.environ["ADRESSE"], os.environ["MOTDEPASSE"]
valeurs = {
    "EMAIL_HOST": "smtp.rssiasservice.online",
    "EMAIL_PORT": "587",
    "EMAIL_USE_TLS": "True",
    "EMAIL_HOST_USER": adresse,
    "EMAIL_HOST_PASSWORD": motdepasse,
    # L'expediteur DOIT correspondre a la boite authentifiee : la plupart des
    # serveurs refusent d'expedier au nom d'une autre adresse.
    "DEFAULT_FROM_EMAIL": f"RSSI as a Service <{adresse}>",
}
lignes = open(chemin, encoding="utf-8").read().splitlines()
vues = set()
sortie = []
for l in lignes:
    cle = l.split("=", 1)[0] if "=" in l else None
    if cle in valeurs:
        sortie.append(f"{cle}={valeurs[cle]}"); vues.add(cle)
    else:
        sortie.append(l)
for cle, v in valeurs.items():
    if cle not in vues:
        sortie.append(f"{cle}={v}")
open(chemin, "w", encoding="utf-8").write("\n".join(sortie) + "\n")
PY
chmod 600 "$ENV_FILE"
echo "Configuration ecrite. Redemarrage des services..."

cd "$PROJET"
$COMPOSE up -d >/dev/null 2>&1
sleep 12

echo "Envoi d'un message de test vers $adresse ..."
DEST="$adresse" $COMPOSE exec -T -e DEST="$adresse" web python -c "
import os
from django.core.mail import send_mail
import django; django.setup()
try:
    n = send_mail(
        subject='Test d envoi — RSSI as a Service',
        message='Si vous lisez ceci, l envoi d emails de la plateforme fonctionne.\n\nCe message a ete envoye automatiquement lors de la configuration.',
        from_email=None,
        recipient_list=[os.environ['DEST']],
        fail_silently=False,
    )
    print('ENVOI ACCEPTE par le serveur —', n, 'message(s). Verifiez votre boite.')
except Exception as e:
    print('ECHEC :', type(e).__name__, '-', str(e)[:220])
    raise SystemExit(1)
"
