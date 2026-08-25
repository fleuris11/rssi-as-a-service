#!/usr/bin/env bash
# Envoie une alerte d'exploitation par email.
#
# Séparé de surveillance.sh pour une raison précise : l'envoi passe par le
# conteneur `web`, donc par la configuration SMTP de l'application. Si c'est
# `web` qui est en panne, l'alerte ne partira pas — c'est la limite assumée
# de toute surveillance interne, et c'est exactement pourquoi la surveillance
# EXTERNE (UptimeRobot) n'est pas optionnelle.
#
# Usage : surveillance-envoi.sh "sujet" "corps"
set -uo pipefail

PROJET="${PROJET:-$HOME/rssi}"
SUJET="${1:?sujet manquant}"
CORPS="${2:?corps manquant}"

cd "$PROJET"
SUJET="$SUJET" CORPS="$CORPS" docker compose -f docker-compose.prod.yml exec -T \
    -e SUJET="$SUJET" -e CORPS="$CORPS" web python -c "
import os, django
django.setup()
from django.conf import settings
from django.core.mail import send_mail

destinataire = getattr(settings, 'PLATFORM_ALERT_EMAIL', '') or settings.EMAIL_HOST_USER
if not destinataire:
    raise SystemExit('Aucun destinataire : renseigner PLATFORM_ALERT_EMAIL.')

send_mail(
    subject='[Supervision] ' + os.environ['SUJET'],
    message=os.environ['CORPS'],
    from_email=None,
    recipient_list=[destinataire],
    fail_silently=False,
)
print('alerte envoyee a', destinataire)
"
