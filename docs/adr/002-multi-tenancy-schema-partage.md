# ADR 002 — Multi-tenancy par schéma partagé + `tenant_id`

- **Statut** : Adopté, implémenté en Phase 1
- **Date** : 2026-08-04
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

Chaque entreprise cliente (tenant) doit être strictement isolée des autres : un dirigeant de PME ne
doit jamais pouvoir lire ou modifier les données d'une autre entreprise, quelle que soit la
ressource (diagnostic, plan d'action, actifs surveillés, documents générés...). C'est une exigence
de sécurité non négociable (CLAUDE.md, §« Multi-tenancy ») et un point d'exemplarité attendu pour un
produit de cybersécurité.

Dans le même temps, le projet doit rester opérable par une seule personne : la volumétrie attendue
en V1 (TPE/PME, dizaines à quelques centaines de tenants) ne justifie pas une infrastructure lourde,
et chaque option supplémentaire de séparation de données (bases séparées, schémas séparés) a un coût
d'exploitation (sauvegardes, migrations, monitoring) qui croît avec le nombre de tenants.

## Options étudiées

1. **Base de données par tenant.** Isolation maximale (aucun risque de fuite inter-tenant au niveau
   SQL), mais coût d'exploitation qui croît linéairement avec le nombre de clients : migrations à
   rejouer sur N bases, sauvegardes multipliées, connexions DB à gérer dynamiquement. Écarté :
   disproportionné pour la cible TPE/PME et une équipe d'une personne.
2. **Un schéma PostgreSQL par tenant** (ex. via `django-tenants`). Isolation forte au niveau du
   moteur de données, mais complexité opérationnelle significative : migrations à appliquer schéma
   par schéma, routage de connexion par schéma, outillage tiers à maintenir à jour avec chaque
   nouvelle version de Django. Écarté pour la V1 : le gain d'isolation ne compense pas la complexité
   ajoutée à ce stade, et cette option reste réévaluable en V2 si un client à fortes exigences
   contractuelles l'impose.
3. **Schéma partagé avec colonne `tenant_id`** sur chaque table métier, isolation appliquée par la
   couche applicative (manager Django + middleware), avec tests d'étanchéité systématiques en CI.

## Décision

Schéma PostgreSQL partagé. Toute table métier porte une colonne `tenant` (FK vers `Tenant`).
L'isolation est appliquée à deux niveaux complémentaires, implémentés en Phase 1
(`apps/tenants/`) :

1. **`TenantScopedManager`** (`apps/tenants/managers.py`) : le manager *par défaut* (`objects`) de
   tout modèle héritant de `TenantScopedModel` **échoue fermé** — s'il n'y a pas de tenant dans le
   contexte de la requête (`contextvars`, voir `apps/tenants/context.py`), il renvoie un queryset
   vide plutôt que toutes les lignes. Un manager `all_objects` explicite, non filtré, reste
   disponible pour le code de confiance qui doit légitimement traverser les tenants (résolution du
   tenant elle-même, back-office plateforme).
2. **`TenantScopingMiddleware`** (`apps/tenants/middleware.py`) : authentifie la requête via JWT,
   résout l'utilisateur, puis — si l'en-tête `X-Tenant-Id` est présent — vérifie qu'une `Membership`
   existe entre cet utilisateur et ce tenant (recherche non filtrée, volontairement, puisque c'est
   elle qui établit le contexte). En l'absence de `Membership` correspondante, la requête est
   rejetée (403) **avant** d'atteindre la vue, et aucun tenant n'est placé dans le contexte.

Toute nouvelle ressource métier exposée par l'API doit hériter de `TenantScopedModel` et être
couverte par un test d'étanchéité (CLAUDE.md, CI) — voir `apps/tenants/tests/test_isolation.py`
pour les scénarios couverts (absence d'en-tête, tenant étranger, tenant inexistant, appartenance
révoquée).

## Conséquences

**Positives**
- Une seule base à sauvegarder, migrer et superviser : coût d'exploitation constant quel que soit
  le nombre de tenants, cohérent avec un VPS unique (ADR-007).
- Migrations Django standards (`makemigrations` / `migrate`), sans outillage tiers à maintenir.
- Le choix « manager par défaut = manager scopé, échoue fermé » rend l'erreur la plus probable (un
  développeur qui oublie de filtrer par tenant) **sûre par défaut** : elle produit un résultat vide,
  jamais une fuite vers un autre tenant. C'est une propriété plus forte qu'une simple convention
  documentée — vérifiée par tests dès la Phase 1.

**Négatives / points de vigilance**
- L'isolation dépend intégralement de la couche applicative : un bug qui contournerait
  `TenantScopedManager` (ex. usage direct de `all_objects` sans filtre explicite hors d'un contexte
  de confiance) romprait l'isolation sans qu'aucune contrainte SQL ne le détecte. Mitigé par : (a)
  la règle « `all_objects` n'est utilisé qu'avec un filtre tenant explicite ou dans du code de
  résolution de tenant » documentée dans le code, (b) l'obligation de test d'étanchéité pour toute
  nouvelle ressource, rappelée dans CLAUDE.md et vérifiée en revue.
- Toutes les données de tous les tenants partagent les mêmes tables : une requête non indexée ou
  un incident de performance peut, en théorie, affecter tous les tenants à la fois (contrairement à
  une base par tenant). Acceptable à la volumétrie visée en V1 ; à surveiller si la base de clients
  grandit fortement.
- Cette option reste réévaluable (schéma par tenant, cf. option 2) si un client impose
  contractuellement une isolation physique plus forte — décision qui ferait l'objet d'un nouvel ADR.
