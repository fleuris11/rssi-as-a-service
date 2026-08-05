# ADR 006 — PostgreSQL seul (+ partitionnement), pgvector en V2 pour le RAG

- **Statut** : Adopté
- **Date** : 2026-08-05
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

Le projet stocke trois familles de données de nature très différente sur la même base de vie que le
reste du produit : les données métier classiques (tenants, comptes, diagnostics, plan d'action), des
séries temporelles à fort volume (`apps.monitoring.CheckResult`, un enregistrement par actif et par
type de check à chaque exécution périodique — potentiellement plusieurs dizaines de milliers de
lignes par mois même à l'échelle d'un petit portefeuille de tenants), et, à terme (V2, hors périmètre
du MVP), des embeddings vectoriels pour un assistant IA capable de rechercher dans le référentiel
ANSSI et les documents générés (RAG — retrieval-augmented generation).

Avec une équipe d'une personne et un budget d'infrastructure VPS (ADR-007), la question est de savoir
combien de moteurs de données différents opérer, et comment absorber la croissance des séries
temporelles sans dégrader le reste de l'application.

## Options étudiées

1. **Base vectorielle dédiée** (Pinecone, Weaviate, Qdrant) pour le futur RAG. Écarté pour le MVP :
   un service supplémentaire à opérer, sécuriser et payer, pour un besoin qui n'existe pas avant la
   V2 ; duplique la logique de tenant-scoping déjà en place côté PostgreSQL (ADR-002), qu'il faudrait
   réimplémenter dans un système tiers.
2. **TimescaleDB** (extension PostgreSQL spécialisée séries temporelles) pour `CheckResult`. Écarté :
   apporte de la compression et des continuous aggregates plus avancés que ce dont le volume actuel a
   besoin, au prix d'une extension supplémentaire à maintenir à jour et d'un couplage plus fort avec
   une distribution PostgreSQL précise (moins portable qu'un PostgreSQL standard sur le VPS ciblé par
   l'ADR-007).
3. **PostgreSQL seul**, avec des index dédiés et des rollups applicatifs pour maîtriser le volume des
   séries temporelles, et l'extension native `pgvector` activée en V2 quand le besoin de RAG devient
   réel.

## Décision

Un seul moteur de données pour tout le projet : PostgreSQL 16 (cf. `docker-compose.yml`,
`backend/config/settings.py:DATABASES`). Les séries temporelles de surveillance
(`apps.monitoring.models.CheckResult`) restent des lignes PostgreSQL classiques, avec un index
composite `["asset", "check_type", "-checked_at"]` (`apps/monitoring/models.py`) pour les lectures les
plus fréquentes (dernier résultat par actif/type, calcul du taux de disponibilité sur une fenêtre
glissante — voir `services.compute_uptime_percentage`). La maîtrise du volume repose sur deux leviers
applicatifs plutôt que sur un moteur spécialisé : une périodicité de check raisonnée (Green IT, cf.
CLAUDE.md) et, si la volumétrie l'exige au-delà du MVP, des rollups (agrégation des `CheckResult`
anciens en résumés quotidiens) — non implémentés à ce stade car le volume actuel ne le justifie pas
encore, mais l'index composite est structuré pour rendre cette évolution non bloquante.

Pour le RAG de l'assistant IA (V2, hors périmètre des phases 1 à 6 actuelles), la décision anticipée
est d'utiliser l'extension `pgvector` de PostgreSQL plutôt qu'un service vectoriel séparé, dès lors
que le besoin apparaît concrètement.

## Conséquences

**Positives**
- Un seul moteur à exploiter, sauvegarder et sécuriser (permissions, chiffrement au repos côté VPS,
  accès réseau) — cohérent avec la contrainte d'une équipe d'une personne.
- Le tenant-scoping (`TenantScopedManager`, ADR-002) s'applique uniformément, y compris aux futures
  tables d'embeddings : pas de logique d'isolation à dupliquer dans un système tiers.
- `pgvector` est mûr et suffisant pour la taille de corpus attendue (référentiel ANSSI + documents
  générés par tenant, pas un corpus web à grande échelle) : pas de sur-ingénierie.

**Négatives / points de vigilance**
- Sans moteur spécialisé, la compression et les agrégations continues des séries temporelles restent
  à la charge de l'application (rollups à écrire quand le volume le justifiera) plutôt qu'automatiques
  comme le proposerait TimescaleDB — dette explicitement acceptée et à réévaluer si la volumétrie de
  `CheckResult` croît significativement au-delà des hypothèses du MVP.
- `pgvector` sur une base déjà sollicitée par l'OLTP applicatif partage les mêmes ressources CPU/IO
  que le reste du produit ; à surveiller si le RAG est activé en V2 avec un corpus qui grossit vite.
