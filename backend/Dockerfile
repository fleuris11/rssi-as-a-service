FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# WeasyPrint (export PDF de la charte informatique, US-4.1) a besoin de
# Pango/Cairo/GDK-Pixbuf au niveau système — non fournis par l'image Python
# slim. Voir aussi .github/workflows/ci.yml, qui installe les mêmes paquets
# pour que les tests d'export PDF s'exécutent en CI.
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
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libcairo2 \
        libffi8 \
        shared-mime-info \
        fonts-liberation \
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
