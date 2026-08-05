FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# WeasyPrint (export PDF de la charte informatique, US-4.1) a besoin de
# Pango/Cairo/GDK-Pixbuf au niveau système — non fournis par l'image Python
# slim. Voir aussi .github/workflows/ci.yml, qui installe les mêmes paquets
# pour que les tests d'export PDF s'exécutent en CI.
RUN apt-get update \
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
