FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Bibliothèques système de WeasyPrint (exports PDF : documents, rapport de
# comité, factures). Aucune n'est fournie par l'image Python slim, et
# WeasyPrint ne les déclare pas à pip : il les ouvre à l'exécution. Une
# bibliothèque absente ne casse donc ni la construction ni le démarrage — elle
# casse le premier PDF demandé. `config/verification_pdf.py` tente une vraie
# génération DANS l'image construite (job CI `container-scan`) : c'est ce test,
# pas cette liste, qui fait foi.
#
# Relevé le 15/09/2026 sur WeasyPrint 70.0 (text/ffi.py) — ce qu'il ouvre :
#   libpango-1.0-0       mise en page du texte (chargement obligatoire)
#   libpangoft2-1.0-0    rendu des polices via FreeType (obligatoire) ; n'était
#                        présente que par dépendance de libpangocairo : retirer
#                        celle-ci l'aurait emportée sans bruit
#   libharfbuzz0b        mise en forme des glyphes (obligatoire)
#   libharfbuzz-subset0  sous-ensemble des polices intégrées au PDF. Facultative
#                        en 70.0 — sans elle WeasyPrint se rabat sur fontTools
#                        et prévient qu'elle « sera requise par les versions
#                        futures ». C'est l'oubli que ce bloc corrige.
#   libfontconfig1       découverte des polices installées (obligatoire)
#   (libgobject, libglib) viennent avec Pango : leur nom de paquet change d'une
#                        version de Debian à l'autre (suffixe t64), on ne les
#                        épingle pas ici
# Ce qu'il n'ouvre pas, mais qui reste nécessaire :
#   fonts-liberation     l'image slim ne contient AUCUNE police ; sans elle, pas
#                        de texte dans le PDF
#   libffi8              requise par le module ctypes de Python lui-même ; déjà
#                        dans l'image de base, listée pour ne pas en dépendre
# Ce qu'aucune version de WeasyPrint ≥ 53 n'ouvre plus (rendu Cairo abandonné) :
#   libpangocairo-1.0-0, libcairo2, libgdk-pixbuf-2.0-0, shared-mime-info
#   Conservées dans ce correctif, qui ajoute sans rien retirer : leur retrait
#   est une décision à part, mesurée dans docs/journal.md (15/09/2026).
#
# Voir aussi .github/workflows/ci.yml, qui installe le même jeu pour les tests.
# `apt-get upgrade` avant l'installation : sans lui, tout paquet hérité de
# l'image de base reste figé à la version qu'elle embarquait, même quand le
# dépôt Debian publie un correctif de sécurité. C'est ainsi que l'image a
# traîné OpenSSL 3.5.6 (CVE-2026-14456) alors que 3.5.7 était disponible — un
# défaut qui n'a rien de propre à ce CVE et qui se reproduirait à chaque
# décalage entre l'image de base et les dépôts.
#
# La contrepartie assumée : deux constructions du même Dockerfile à des dates
# différentes ne produisent plus exactement la même image. C'est le comportement
# voulu ici — une image reconstruite à chaque déploiement doit embarquer les
# correctifs publiés depuis, pas ceux d'un instantané amont.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libharfbuzz-subset0 \
        libfontconfig1 \
        fonts-liberation \
        libffi8 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Invoked via "sh" (not exec bit) so it still works when a dev bind-mount
# (docker-compose) overwrites the file and drops the executable permission.
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
