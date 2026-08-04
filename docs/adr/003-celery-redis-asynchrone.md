# ADR 003 — Celery + Redis pour l'asynchrone

- **Statut** : Adopté ; infrastructure présente dès la Phase 1 (Redis, cache), exécution des tâches
  prévue en Phase 3 (surveillance) et Phase 4 (IA)
- **Date** : 2026-08-04
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

Plusieurs traitements de la plateforme ne doivent jamais s'exécuter dans le cycle requête/réponse
HTTP synchrone :
- les appels à l'API Claude (génération documentaire, météo cyber) prennent typiquement 30 à 60
  secondes — bien au-delà d'un timeout HTTP raisonnable ;
- les checks de surveillance (HTTP, TLS, DNS) sont des appels réseau sortants, par nature lents et
  parfois défaillants (timeouts, hôtes injoignables) ;
- l'envoi d'emails (météo quotidienne, alertes) ne doit pas bloquer une requête utilisateur.

Ces traitements ont aussi besoin d'être **planifiés** (météo envoyée à l'heure choisie par chaque
client, checks périodiques par type d'actif) et d'être **fiables** : un appel IA ou un check réseau
qui échoue transitoirement doit pouvoir être réessayé (avec backoff) sans dupliquer d'effet de bord
(CLAUDE.md : « les tasks Celery doivent être idempotentes et retryables »).

## Options étudiées

1. **Tâches cron système + scripts autonomes.** Simple à comprendre, mais aucune intégration native
   avec l'ORM Django/l'état applicatif, pas de retry structuré, pas de visibilité sur les échecs,
   difficile à idempotencer proprement. Écarté.
2. **Appels synchrones (ou multithreading applicatif) dans la requête HTTP.** Écarté d'emblée :
   viole directement la contrainte « jamais d'appel IA dans le cycle requête HTTP » (CLAUDE.md) et
   dégraderait fortement l'UX pour les checks réseau.
3. **RQ (Redis Queue).** Plus simple à opérer que Celery, mais moins riche pour la planification
   récurrente (l'équivalent de Celery Beat existe mais est moins mature) et pour la gestion fine de
   plusieurs files avec des politiques de retry différenciées. Écarté au profit de l'option plus
   riche, l'écart de complexité d'exploitation avec Celery restant faible une fois Redis déjà
   présent comme dépendance (cache).
4. **Celery + Redis** (broker et result backend) + **Celery Beat** pour la planification.

## Décision

Celery + Redis, avec **des files séparées par domaine de charge** : `ai` (appels API Claude),
`monitoring` (checks réseau), `emails` (envois transactionnels et météo quotidienne). Cette
séparation permet de dimensionner et de surveiller chaque type de charge indépendamment, et
d'éviter qu'un pic de checks de surveillance ne retarde l'envoi d'un email d'alerte critique, par
exemple. Celery Beat planifie les checks périodiques (fréquence dépendante du type d'actif), la
génération des météos (par fuseau/heure choisie par le client) et les recalculs de score.

Chaque tâche doit être **idempotente** (clé d'idempotence dérivée de l'entité traitée) et
**retryable** (backoff exponentiel), conformément à CLAUDE.md.

Redis est déjà provisionné dans `docker-compose.yml` et configuré comme backend de cache Django
dès la Phase 1 (`CACHES` dans `config/settings.py`), précisément pour éviter d'introduire ce
composant d'infrastructure en urgence lors de la Phase 3 — il est mis en place et vérifié
(`docker compose up`) avant d'en avoir un usage fonctionnel. Les workers et Celery Beat eux-mêmes
ne sont volontairement **pas** ajoutés à `docker-compose.yml` en Phase 1 (scope explicite de la
session de socle) ; ils arriveront avec les premières tâches réelles en Phase 3.

## Conséquences

**Positives**
- Écosystème mature et bien intégré à Django (`django-celery-beat` si besoin d'une planification
  pilotable en base plus tard), retry/backoff natifs, supervision possible via Flower si le besoin
  s'en fait sentir.
- La séparation en files isole les pannes : un fournisseur IA en incident n'affecte pas l'envoi des
  emails d'alerte ni les checks de surveillance.
- Introduire Redis dès le socle (Phase 1) évite un changement d'infrastructure disruptif en Phase 3.

**Négatives / points de vigilance**
- Composant opérationnel supplémentaire : un worker ou Beat arrêté silencieusement doit être
  détecté (heartbeat prévu dans l'observabilité, cadrage §10) — sans quoi les checks de surveillance
  ou la météo quotidienne cesseraient silencieusement de s'exécuter.
- Les tests d'intégration doivent utiliser le mode *eager* de Celery (exécution synchrone en test)
  pour rester déterministes et rapides en CI, comme prévu au plan de tests (cadrage §9).
- La discipline d'idempotence doit être appliquée dès la première tâche écrite (Phase 3) — un oubli
  serait difficile à corriger rétroactivement sans risque de double effet de bord en production
  (ex. double envoi d'alerte).
