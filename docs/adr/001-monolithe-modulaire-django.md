# ADR 001 — Monolithe modulaire Django

- **Statut** : Adopté
- **Date** : 2026-08-04
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

Le projet est développé par une seule personne, sur ~14 semaines à plus de 10h/semaine (cadrage
§11), avec un double objectif : livrer une plateforme réelle sur `rssiasservice.online` et
constituer un dossier de certification (Blocs 2, 3, 4). Le périmètre fonctionnel couvre huit
domaines métier distincts (comptes/tenants, diagnostic ANSSI, plan d'action, surveillance,
génération documentaire IA, notifications, back-office) qui devront évoluer indépendamment au fil
des phases (cadrage §11), sans que l'équipe (une personne aujourd'hui, une petite équipe envisagée
en V2 selon le scénario Bloc 4) n'ait la capacité d'opérer plusieurs services déployés séparément.

Il faut donc choisir une architecture qui : (1) reste opérable seul avec un budget d'infrastructure
minimal, (2) impose une discipline de frontières entre domaines suffisante pour ne pas devenir un
« monolithe boueux » illisible, et (3) n'interdise pas une extraction future en services séparés si
un besoin de passage à l'échelle apparaît (scénario Bloc 4).

## Options étudiées

1. **Microservices dès le départ** (un service Django/FastAPI par domaine métier, déployés et
   orchestrés séparément). Écarté : complexité opérationnelle (réseau inter-services, cohérence des
   données, observabilité distribuée, CI/CD multipliée) disproportionnée pour une équipe d'une
   personne et un MVP ; aucun besoin de scaling différencié identifié à ce stade.
2. **Monolithe non structuré** (une seule app Django fourre-tout, ou des apps sans règle
   d'isolation entre elles). Écarté : dette technique quasi garantie sur un projet de cette taille
   fonctionnelle (8 domaines) et sur cette durée ; rend une extraction future beaucoup plus
   coûteuse ; nuit à la lisibilité attendue dans un dossier de certification Bloc 2.
3. **Monolithe modulaire** : apps Django par domaine métier (`accounts`, `tenants`, `assessments`,
   `actions`, `monitoring`, `ai_assistant`, `notifications`, `platform_admin`), chacune exposant une
   interface explicite (`services.py`) ; aucune app n'importe directement les modèles d'une autre.

## Décision

Monolithe modulaire Django + DRF. Chaque domaine métier est une app Django distincte avec ses
propres modèles, vues, permissions et tests. Les dépendances croisées entre apps passent
exclusivement par les fonctions publiques de `services.py` de l'app concernée — jamais par un
import direct de modèle d'une autre app. Cette règle est déjà appliquée en Phase 1 :
`apps/accounts/serializers.py` ne touche jamais aux modèles de `apps/tenants` directement, il
appelle `apps.tenants.services.create_tenant_with_owner()` et
`apps.tenants.services.list_user_memberships()`.

Le déploiement reste un seul processus Django (Gunicorn) + des workers Celery partageant la même
base de code, orchestrés par un unique `docker-compose.yml`, sur un VPS unique (voir aussi
ADR-007 pour le choix d'infrastructure, à rédiger).

## Conséquences

**Positives**
- Un seul dépôt, un seul pipeline CI, un seul environnement à opérer : coût d'exploitation minimal
  compatible avec une équipe d'une personne et un budget freelance.
- Les migrations de base de données restent celles, standards, d'un projet Django unique — pas de
  cohérence distribuée à gérer entre plusieurs bases.
- Les frontières de modules (apps + `services.py`) documentent explicitement les responsabilités de
  chaque domaine, ce qui sert directement le dossier Bloc 2 (architecture) et rend une extraction
  future en service autonome réaliste si un besoin de scaling différencié apparaît (ex. les checks
  de surveillance ou les appels IA, plus gourmands en ressources que le reste).

**Négatives / points de vigilance**
- La discipline « pas d'import de modèle cross-app » n'est pas imposée mécaniquement par Django ;
  elle dépend de la revue de code et, à terme, pourrait être vérifiée par une règle de lint dédiée
  (ex. `flake8-tidy-imports` / règle d'architecture personnalisée) si le projet grandit.
- Toutes les apps partagent la même base PostgreSQL : un incident de performance ou de verrouillage
  sur une app (ex. checks de surveillance à fort volume) peut affecter les autres. Mitigé en
  partie par Celery + files séparées (ADR-003) qui isolent au moins la charge asynchrone.
- Le scaling reste essentiellement vertical (un VPS plus gros) tant que le monolithe n'est pas
  scindé ; acceptable pour la cible TPE/PME du MVP, à réévaluer si la base d'utilisateurs grandit
  fortement (scénario documenté dans le cadrage Bloc 4).
