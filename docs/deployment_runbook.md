# Runbook de déploiement — rssiasservice.online

> **État au 2026-08-13.** Le domaine `rssiasservice.online` résout vers
> `194.126.193.53` et sert **la page de parking par défaut de LWS** : aucune
> instance de l'application n'est déployée à ce jour, et aucun VPS n'est
> provisionné. Ce document est la procédure à exécuter pour y remédier ; il
> n'est **pas** le compte rendu d'un déploiement réalisé.

Chaque étape se termine par une **vérification observable**. Ne pas passer à
la suivante sans l'avoir constatée : la moitié des incidents de déploiement
viennent d'une étape supposée faite.

---

## 0. Prérequis

- Un VPS (2 vCPU / 4 Go / 40 Go suffisent pour le volume visé), Debian 12 ou
  Ubuntu 24.04, avec Docker et le plugin Compose.
- L'enregistrement DNS `A` (et `AAAA` si IPv6) de `rssiasservice.online` **et**
  `www.rssiasservice.online` pointant vers l'IP du VPS. Tant que le domaine
  pointe vers l'hébergement mutualisé LWS, Caddy ne pourra pas obtenir de
  certificat.
- Les accès : SSH au VPS, panneau DNS du registrar, compte Breachsense.

```bash
# Vérification : le domaine pointe bien vers le VPS
dig +short rssiasservice.online          # doit renvoyer l'IP du VPS
```

---

## 1. Secrets de production

Générer **trois clés Fernet distinctes**. Ne jamais réutiliser une clé d'un
usage à l'autre : le garde-fou de démarrage (§3) refusera de booter, mais
mieux vaut ne pas y arriver.

```bash
for i in 1 2 3; do
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
done
python -c "import secrets; print(secrets.token_urlsafe(64))"   # DJANGO_SECRET_KEY
```

Créer `/opt/rssi/.env` sur le VPS (jamais dans le dépôt) :

```env
DJANGO_SETTINGS_MODULE=config.settings_production
DJANGO_SECRET_KEY=<token_urlsafe ci-dessus>
DJANGO_ALLOWED_HOSTS=rssiasservice.online,www.rssiasservice.online
DATABASE_URL=postgres://rssiasservice:<mot de passe fort>@postgres:5432/rssiasservice
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/1
CORS_ALLOWED_ORIGINS=https://rssiasservice.online
FRONTEND_BASE_URL=https://rssiasservice.online

AI_PSEUDONYMIZATION_KEY=<clé Fernet 1>
TOTP_ENCRYPTION_KEY=<clé Fernet 2>
BREACH_SECRET_ENCRYPTION_KEY=<clé Fernet 3>

ANTHROPIC_API_KEY=<clé API>
BREACHSENSE_LICENSE_KEY=<licence>
BREACHSENSE_MODE=live
BREACHSENSE_WEBHOOK_USERNAME=<identifiant choisi>
BREACHSENSE_WEBHOOK_PASSWORD=<mot de passe fort choisi>
BREACHSENSE_WEBHOOK_CALLBACK_URL=https://rssiasservice.online/api/v1/webhooks/breachsense

EMAIL_HOST=<smtp>
EMAIL_HOST_USER=<user>
EMAIL_HOST_PASSWORD=<mot de passe>
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
```

```bash
chmod 600 /opt/rssi/.env    # vérification : -rw------- pour le seul owner
```

---

## 2. Démarrage de la stack

```bash
git clone https://github.com/fleuris11/rssi-as-a-service.git /opt/rssi/app
cd /opt/rssi/app
docker compose -f docker-compose.prod.yml --env-file /opt/rssi/.env up -d --build
```

**Vérification :**

```bash
docker compose -f docker-compose.prod.yml ps
# Attendu : web, worker, beat, postgres, redis, caddy — tous "Up",
# postgres/redis/worker/beat en "(healthy)".
```

---

## 3. Le garde-fou de configuration a bien mordu

Ce contrôle (`config/startup_checks.py`) s'exécute **à l'import des settings**,
donc avant que Gunicorn ne serve quoi que ce soit.

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py check --deploy
```

**Attendu :** `System check identified no issues`. Si une clé est manquante,
invalide ou réutilisée, le conteneur `web` sera en boucle de redémarrage et
`docker compose logs web` affichera `ImproperlyConfigured` avec la liste
complète des problèmes (ils sont tous rapportés d'un coup, pas un par
redémarrage).

---

## 4. HTTPS et certificat

Caddy demande le certificat à Let's Encrypt au premier démarrage ; compter
quelques dizaines de secondes.

```bash
curl -I https://rssiasservice.online                  # attendu : 200
curl -sI https://rssiasservice.online | grep -i strict-transport-security
echo | openssl s_client -connect rssiasservice.online:443 -servername rssiasservice.online 2>/dev/null \
  | openssl x509 -noout -issuer -dates
```

**Attendu :** `issuer=...Let's Encrypt...`, `notAfter` à ~90 jours, en-tête
HSTS présent. En cas d'échec : `docker compose logs caddy` — la cause est
presque toujours un DNS pas encore propagé (§0).

---

## 5. Celery : worker ET beat tournent réellement

Ne pas se contenter de « le conteneur est Up » : un worker peut démarrer sans
consommer aucune file.

```bash
# Le worker répond et déclare ses files
docker compose -f docker-compose.prod.yml exec worker celery -A config inspect active_queues \
  | grep -E "monitoring|emails|ai"

# Beat a réellement DÉCLENCHÉ une tâche (et pas seulement démarré)
docker compose -f docker-compose.prod.yml logs beat | grep -i "Scheduler: Sending due task"
docker compose -f docker-compose.prod.yml logs worker | grep -iE "succeeded|received"
```

**Attendu :** les trois files listées côté worker ; au moins une ligne
`Sending due task` côté beat **et** son exécution côté worker. Les tâches
planifiées les plus fréquentes (checks de surveillance) donnent le signal le
plus rapide ; sinon, forcer :

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py shell -c \
  "from apps.monitoring.tasks import run_scheduled_checks; print(run_scheduled_checks.delay())"
```

---

## 6. Webhook Breachsense de bout en bout

C'est la **seule dépense de quota justifiée** de cette étape.

```bash
# 6.1 Déclarer les identifiants Basic Auth côté Breachsense
docker compose -f docker-compose.prod.yml exec web python manage.py configure_webhook_credentials

# 6.2 Déclencher une notification de test depuis Breachsense
docker compose -f docker-compose.prod.yml exec web python manage.py account_test
```

**Vérifications, dans l'ordre :**

```bash
# a) La requête entrante est bien arrivée et authentifiée (pas de 401)
docker compose -f docker-compose.prod.yml logs caddy | grep webhooks/breachsense

# b) Elle a été traitée sans erreur
docker compose -f docker-compose.prod.yml logs web | grep -i breachsense

# c) Une notification de test est reconnue comme telle et n'est PAS persistée
#    (comportement attendu : `is_test` est ignoré à l'ingestion, cf. Phase 7)
```

Pour valider la chaîne **jusqu'à l'email**, utiliser une fuite simulée plutôt
qu'une notification de test (aucun quota consommé, chemin d'ingestion réel) :

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py simulate_breach_finding \
  --tenant-slug <slug> --asset-value <actif déclaré>
```

**Attendu :** le finding apparaît dans `/exposition`, et l'email d'alerte part
(`docker compose logs worker | grep -i mail`).

---

## 7. Tenant de démonstration

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py seed_demo_tenant \
  --reset --allow-production
```

Le drapeau `--allow-production` est **obligatoire** hors DEBUG : la commande
refuse de s'exécuter sans lui, précisément pour qu'un seed de démo ne parte
jamais par accident sur une base client.

**Vérification (visuelle, à faire dans le navigateur) :** le tenant s'affiche
`Demo — Cabinet Comptable Durand`, ses actifs sont tous en
`*.cabinet-durand-demo.fr`, et les comptes sont en `@cabinet-durand-demo.fr`.
Le préfixe `Demo — ` et le domaine `-demo.fr` rendent la confusion avec un
tenant réel impossible d'un coup d'œil.

---

## 8. Contrôles de sécurité finaux

```bash
# DEBUG désactivé : une URL inexistante ne doit PAS afficher de traceback
curl -s https://rssiasservice.online/api/v1/inexistant | head -c 200

# ALLOWED_HOSTS strict : un Host inconnu doit être rejeté
curl -sI -H "Host: evil.example" https://rssiasservice.online | head -1   # attendu : 400

# Les secrets ne sont pas dans le dépôt
cd /opt/rssi/app && git status --porcelain    # .env ne doit jamais apparaître
```

---

## Rotation d'une clé de chiffrement (sans coupure)

Procédure complète : voir `docs/adr/014-secret-handling-breach-data.md` §5.
En résumé, sur le VPS :

```bash
NEW=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
# 1. Nouvelle clé EN PREMIER, ancienne conservée pour le déchiffrement
#    BREACH_SECRET_ENCRYPTION_KEYS=<nouvelle>,<ancienne>
docker compose -f docker-compose.prod.yml restart web worker beat
# 2. Re-chiffrer l'existant (idempotent, rejouable)
docker compose -f docker-compose.prod.yml exec web python manage.py rotate_breach_secret_key
# 3. Retirer l'ancienne clé, redémarrer
```

Vérification : `rotate_breach_secret_key` relancé une seconde fois doit
rapporter `0` secret re-chiffré.

---

## Si quelque chose échoue

| Symptôme | Cause la plus fréquente |
|---|---|
| `web` redémarre en boucle | Garde-fou de configuration (§3) — lire `docker compose logs web`, la liste des problèmes y est complète |
| Pas de certificat | DNS pas encore propagé, ou port 80 fermé (Let's Encrypt en a besoin) |
| Webhook en 401 | Identifiants Basic Auth non déclarés côté Breachsense (§6.1) |
| Beat démarre mais rien ne s'exécute | Worker non abonné aux bonnes files — vérifier `inspect active_queues` |
| Emails non partis | `DJANGO_EMAIL_BACKEND` resté sur le backend console |
