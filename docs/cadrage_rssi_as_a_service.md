# Document de cadrage — RSSI as a Service
### Plateforme SaaS de conformité et de surveillance cybersécurité pour TPE/PME
*Projet freelance — support de validation RNCP38822 (EADL, niveau 7) — Blocs 2, 3 et 4 (+ appui Bloc 1)*
*Domaine cible : https://rssiasservice.online — Version 1.0 — Août 2026*

---

## 1. Contexte et problématique

### 1.1 Le constat
Les TPE/PME françaises subissent une triple pression en matière de cybersécurité :

1. **Pression réglementaire** : la directive européenne NIS2 (transposée en France) étend les obligations de cybersécurité à des milliers d'entités qui en étaient exemptées, en plus du RGPD déjà applicable à toutes.
2. **Pression commerciale** : les grands donneurs d'ordre (banques, assurances, industriels) exigent de leurs sous-traitants des questionnaires de sécurité complets avant contractualisation. Les cyber-assureurs conditionnent leurs tarifs (voire l'assurabilité) à des preuves de maturité.
3. **Pression de la menace** : les PME sont les premières victimes des ransomwares, précisément parce qu'elles sont peu protégées.

### 1.2 Le problème
Face à ces exigences, la PME type (10-250 salariés) n'a :
- **ni les compétences internes** : pas de RSSI (coût d'un RSSI : 80-120 k€/an) ;
- **ni le budget conseil** : un accompagnement ISO 27001 se chiffre en dizaines de milliers d'euros ;
- **ni la capacité de compréhension** : le vocabulaire de la cybersécurité et des référentiels est illisible pour un dirigeant non technique.

Elle est donc coincée entre l'obligation de se conformer et l'impossibilité pratique de le faire.

### 1.3 La vision produit
**RSSI as a Service** est un RSSI virtuel en SaaS qui :
- **diagnostique** la maturité cyber de l'entreprise (référentiel ANSSI) ;
- **pilote** un plan d'action priorisé et suivi dans le temps ;
- **rédige** les documents de conformité obligatoires, personnalisés par IA ;
- **répond** aux questions du dirigeant via un assistant contextuel ;
- **surveille en continu** les actifs exposés de l'entreprise (sites, certificats, configuration email, fuites de comptes) et délivre chaque matin une « météo cyber » lisible en 20 secondes.

> **Pitch** : « Votre RSSI virtuel : il vous met en conformité (NIS2, RGPD, ANSSI), il rédige vos documents, il répond à vos questions — et il monte la garde 24h/24 sur vos sites, vos emails et vos outils, avec un point météo chaque matin. »

Le diagnostic **fait entrer** le client ; la surveillance continue **le fait rester** (usage quotidien, rétention de l'abonnement).

### 1.4 Positionnement concurrentiel

| Acteur | Cible | Limite pour notre segment |
|---|---|---|
| Cabinets de conseil / Big 4 | Grands comptes | 1 000-2 000 €/jour, inaccessible aux PME |
| Vanta, Drata (US) | Scale-ups tech | Orientés SOC 2 / marché US, tarifs élevés, vocabulaire expert |
| Tenacy, Egerie (FR) | ETI / grands comptes avec équipe sécurité | Supposent une compétence interne existante |
| Checklists ANSSI en PDF | Tous | Statiques, aucun suivi, aucun accompagnement |

**Différenciateurs** : (1) langage simple orienté dirigeant non technique ; (2) IA comme accompagnateur actif (rédaction, traduction d'alertes, conseil contextuel) ; (3) ancrage réglementaire français/européen (ANSSI, NIS2, RGPD) ; (4) surveillance continue incluse, pensée pour des actifs simples (sites web, email, SaaS).

### 1.5 Modèle économique (esquisse)
- **Formule Découverte (gratuite)** : diagnostic ANSSI + score, 1 actif surveillé.
- **Formule Essentielle (abonnement mensuel)** : plan d'action complet, météo quotidienne, 10 actifs, génération documentaire IA (quota).
- **Formule Sérénité** : actifs illimités, assistant IA illimité, routines de conformité, multi-utilisateurs.

Le modèle n'a pas vocation à être exécuté commercialement dans le cadre de la certification, mais il structure l'étude de faisabilité (Bloc 1) et crédibilise le scénario freelance.

### 1.6 Limites et cadre assumés
- La plateforme est un **outil d'aide au pilotage**, pas un audit certifiant ni un conseil juridique (disclaimer affiché, CGU).
- La surveillance porte **exclusivement sur les actifs déclarés et détenus par le client**, via des vérifications **passives** (lecture de certificats, d'en-têtes HTTP, d'enregistrements DNS publics). Aucun scan intrusif ni test d'intrusion.

---

## 2. Personas et parcours

### 2.1 Personas
- **P1 — Le dirigeant de PME (persona principal)** : 45 ans, dirige un cabinet comptable de 35 personnes. Non technique. Vient de recevoir un questionnaire de sécurité d'un client bancaire et une relance de son cyber-assureur. Objectif : répondre correctement, éviter l'amende et l'attaque, sans embaucher.
- **P2 — Le responsable informatique « couteau suisse »** : seul informaticien d'une PME industrielle de 120 personnes. Compétent mais débordé. Objectif : outiller sa veille, prouver son travail à la direction, prioriser.
- **P3 — Le freelance / la petite agence web** : gère les sites de plusieurs clients. Objectif : surveiller tous les sites clients depuis un seul endroit, être alerté avant le client, vendre un service de sérénité.
- **P0 — L'administrateur plateforme (nous)** : supervision des tenants, des quotas IA, de la santé de la plateforme.

### 2.2 Parcours type (P1)
1. Inscription → création de l'espace entreprise (tenant) → profil (secteur, effectif, outils).
2. Auto-évaluation ANSSI guidée (42 mesures, en langage simple) → score de maturité + radar par domaine.
3. Plan d'action généré automatiquement, priorisé (quick wins → chantiers) → suivi kanban.
4. Déclaration des actifs à surveiller (domaines, URLs) → activation de la météo quotidienne (heure choisie).
5. Génération de la charte informatique personnalisée (IA) → validation → export PDF.
6. Usage récurrent : lecture de la météo le matin, questions à l'assistant, avancement du plan, alertes temps réel si incident.

---

## 3. Périmètre fonctionnel

### 3.1 Modules du MVP (V1 — développé)

#### M1 — Comptes & multi-tenancy
| ID | User story | Priorité |
|---|---|---|
| US-1.1 | En tant que dirigeant, je crée un compte et l'espace de mon entreprise afin de disposer d'un environnement isolé. | Must |
| US-1.2 | En tant qu'admin entreprise, j'invite des collaborateurs avec un rôle (admin / contributeur / lecteur) afin de répartir le travail. | Must |
| US-1.3 | En tant qu'utilisateur, je m'authentifie de façon sécurisée (JWT, verrouillage après échecs, politique de mots de passe) et je peux activer la double authentification (TOTP). | Must (2FA : Should) |
| US-1.4 | En tant qu'admin plateforme, je supervise les tenants (activité, quotas, état) depuis un back-office. | Must |

#### M2 — Diagnostic de maturité (référentiel ANSSI)
| ID | User story | Priorité |
|---|---|---|
| US-2.1 | En tant que dirigeant, je réponds à un questionnaire guidé en langage simple, découpé par domaines, avec sauvegarde de la progression. | Must |
| US-2.2 | En tant que dirigeant, je visualise mon score global et un radar par domaine afin de comprendre mes forces et faiblesses. | Must |
| US-2.3 | En tant que dirigeant, je peux refaire l'évaluation périodiquement et visualiser l'évolution de mon score dans le temps. | Should |

#### M3 — Plan d'action
| ID | User story | Priorité |
|---|---|---|
| US-3.1 | En tant que dirigeant, un plan d'action priorisé est généré à partir de mes écarts (quick wins vs chantiers, effort estimé, impact). | Must |
| US-3.2 | En tant que contributeur, je suis l'avancement des mesures sur un kanban (à faire / en cours / fait) avec assignation. | Must |
| US-3.3 | En tant que dirigeant, la complétion des mesures met à jour mon score de conformité. | Should |

#### M4 — IA : génération documentaire & assistant
| ID | User story | Priorité |
|---|---|---|
| US-4.1 | En tant que dirigeant, je génère une charte informatique personnalisée à partir du contexte de mon entreprise, je la révise et je l'exporte. | Must |
| US-4.2 | En tant que dirigeant, je pose des questions à un assistant qui connaît mon état de conformité et me répond en langage simple. | Must |
| US-4.3 | En tant qu'utilisateur, je visualise avant chaque appel IA les données qui seront transmises (transparence) et l'IA peut être désactivée pour mon tenant. | Must |
| US-4.4 | En tant que plateforme, les données transmises à l'IA sont pseudonymisées (aucun nom d'entreprise, de personne, d'IP) et le fournisseur IA n'entraîne pas ses modèles sur ces données (cadre API). | Must |

#### M5 — Surveillance continue & météo cyber
| ID | User story | Priorité |
|---|---|---|
| US-5.1 | En tant que client, je déclare mes actifs (domaines, URLs) avec preuve de légitimité (case d'engagement + vérification DNS optionnelle). | Must |
| US-5.2 | En tant que client, mes sites sont vérifiés périodiquement (disponibilité HTTP, temps de réponse) et je vois un historique d'uptime. | Must |
| US-5.3 | En tant que client, mes certificats SSL sont surveillés (validité, expiration) avec alerte anticipée (30/14/7 jours). | Must |
| US-5.4 | En tant que client, la configuration email de mon domaine (SPF, DKIM, DMARC) et les en-têtes de sécurité HTTP de mes sites sont analysés avec recommandations. | Must |
| US-5.5 | En tant que client, je reçois chaque matin à l'heure de mon choix une « météo cyber » par email : synthèse ☀️/⚠️/🔴 générée par IA, lisible en 20 secondes. | Must |
| US-5.6 | En tant que client, je reçois une alerte temps réel (email) si un événement critique survient (site down, certificat expiré), selon mes préférences horaires. | Should |
| US-5.7 | En tant que client, mes actifs déclarés sont vérifiés contre des sources de renseignement sur la menace (identifiants volés, fuites de données) et je suis alerté en langage simple en cas de compromission détectée. | Must (Phase 7) |

#### M6 — Renseignement sur la menace (Breachsense) — Phase 7, intégré
US-5.7 ci-dessus est développée via un module dédié (`apps.threat_intelligence`, ADR-013/ADR-014) :
scan de diagnostic ponctuel (quota partagé, palier Essentials : 1000 requêtes/mois) déclenché à la
déclaration d'un actif ou manuellement (garde-fous quota + cooldown), et monitoring continu par
webhook (hors quota, limité à 15 actifs sur la licence partagée). **Remplace** la ligne « Fuites de
comptes (API Have I Been Pwned) » qui figurait en roadmap V2 non développée — voir ADR-013 pour la
justification de ce changement de fournisseur, documentée plutôt que tranchée silencieusement.

### 3.2 Roadmap V2 (architecturée, non développée dans le MVP)
- **Extension Breachsense palier supérieur (« premium-marketplace »)** : le client HTTP
  (`threat_intelligence/providers/breachsense/client.py`) n'implémente que les endpoints du palier
  Essentials actuellement souscrit ; le palier supérieur ajoute un accès marketplace non couvert par
  cette intégration — extension future si le palier de licence évolue.
- **Veille vulnérabilités personnalisée** : croisement du stack déclaré avec les flux CERT-FR/CVE, traduction des alertes en consignes actionnables par IA (RAG).
- **Référentiels additionnels** : NIS2 détaillé, ISO 27001 simplifié, questionnaire RGPD.
- **Routines de conformité** : tâches récurrentes (revue des accès trimestrielle, test de restauration mensuel) avec rappels.
- **Aide aux questionnaires clients** : import d'un questionnaire de sécurité reçu, pré-remplissage assisté par IA à partir du dossier de conformité.
- **Génération documentaire étendue** : PSSI complète, procédure de gestion d'incident, plan de continuité simplifié.
- **Page de statut publique** par tenant (option), multi-langue (EN), application mobile.

### 3.3 Hors périmètre (assumé)
Scan de vulnérabilités intrusif, EDR/antivirus, SIEM, réponse à incident managée, audit certifiant. Ces exclusions sont documentées comme choix de positionnement (produit d'aide au pilotage, vérifications passives uniquement).

---

## 4. Architecture

### 4.1 Vue d'ensemble
Architecture **monolithe modulaire** Django + DRF, frontend React découplé, PostgreSQL, Redis, workers Celery, le tout conteneurisé (Docker) et déployé sur VPS derrière un reverse proxy (Caddy ou Nginx, TLS automatique) sur `rssiasservice.online`.

```
[React SPA (Vite)] --HTTPS--> [Caddy/Nginx] --> [Django + DRF (Gunicorn)]
                                                    |            |
                                             [PostgreSQL]   [Redis]
                                                    |            |
                                          [Celery Workers] <-----+
                                          [Celery Beat (scheduler)]
                                                    |
                    +------ API Claude (IA) ------- + ------ SMTP (emails) ------+
                    +------ Checks HTTP/TLS/DNS sortants (surveillance) ---------+
```

### 4.2 Découpage en apps Django (frontières de modules)
- `accounts` : utilisateurs, authentification JWT, 2FA, rôles.
- `tenants` : entreprises, membres, quotas, scoping.
- `assessments` : référentiels, questionnaires, réponses, scoring.
- `actions` : plan d'action, kanban, assignations.
- `monitoring` : actifs, checks, résultats, historique uptime, moteur d'alertes.
- `ai_assistant` : orchestration des appels IA, pseudonymisation, conversations, génération documentaire, suivi des tokens.
- `notifications` : préférences, météo quotidienne, emails transactionnels.
- `threat_intelligence` (Phase 7) : renseignement sur la menace (Breachsense) — provider abstrait, scan de diagnostic, monitoring webhook, quota/pool partagés par la plateforme.
- `platform_admin` : back-office superviseur (scaffold — le back-office CTI de la Phase 7 est exposé directement par `threat_intelligence`, gardé par `IsAdminUser`, en attendant la construction complète de ce module).

Chaque app expose une interface claire (services) ; les dépendances croisées passent par ces services, jamais par les modèles internes d'une autre app — condition d'une extraction future en service autonome si le besoin de scaling apparaît.

### 4.3 Multi-tenancy
Schéma partagé PostgreSQL avec `tenant_id` sur toutes les tables métier + **middleware de scoping** systématique (résolution du tenant depuis le JWT, filtrage automatique via des managers Django dédiés). Tests d'étanchéité dédiés (un tenant ne peut jamais lire les données d'un autre) exécutés en CI.

### 4.4 Traitements asynchrones
Celery + Redis :
- **Celery Beat** planifie : checks de surveillance (périodicité par type d'actif), génération des météos (par fuseau/heure choisie), recalculs de score.
- **Workers** exécutent : appels IA (30-60 s, jamais dans le cycle requête/réponse HTTP), checks réseau sortants, envois d'emails. Retry avec backoff, idempotence par clé de tâche, files séparées (`ai`, `monitoring`, `emails`) pour isoler les charges.

### 4.5 Pipeline IA (privacy by design)
1. Construction du contexte minimal nécessaire au cas d'usage (profil : secteur, effectif, réponses agrégées — jamais de PII).
2. **Couche de pseudonymisation** : remplacement des identifiants réels (raison sociale, noms, domaines) par des placeholders ; table de correspondance conservée côté serveur uniquement.
3. Appel API Claude — **Haiku** pour classification/extraction/synthèses courtes (météo), **Sonnet** pour génération documentaire longue.
4. Ré-injection des identifiants réels dans la réponse, validation humaine avant export.
5. Journalisation : cas d'usage, volume de tokens, coût — par tenant (quotas + Green IT).

### 4.6 Modèle de données (entités principales)
`Tenant` (1—N) `Membership` (N—1) `User` · `Tenant` (1—N) `Assessment` (1—N) `Answer` (N—1) `Measure` (N—1) `Referential` · `Tenant` (1—N) `ActionItem` · `Tenant` (1—N) `Asset` (1—N) `CheckResult` · `Asset` (1—N) `Alert` · `Tenant` (1—N) `AIJob` / `Document` / `Conversation` · `Tenant` (1—1) `NotificationPreferences` · `Asset` (0—1) `MonitoredAsset` (pool Breachsense, 15 slots partagés) · `Asset` (1—N) `BreachFinding` (Phase 7, jamais de secret en clair) · `Tenant` (1—N) `BreachIntelligenceUsage` / `BreachScanJob`.
Les résultats de checks (séries temporelles) sont partitionnés par mois et agrégés (rollups quotidiens) pour maîtriser la volumétrie.

---

## 5. Registre des décisions d'architecture (ADR)

Chaque décision majeure fait l'objet d'un ADR complet dans le dépôt (`docs/adr/NNN-titre.md`) au format : Contexte → Options étudiées → Décision → Conséquences. Registre initial :

| # | Décision | Alternatives écartées | Justification synthétique |
|---|---|---|---|
| 001 | Monolithe modulaire Django | Microservices ; monolithe non structuré | Équipe de 1, pas de besoin de scaling différencié au MVP ; frontières de modules nettes préservant une extraction future ; coût opérationnel minimal. |
| 002 | Multi-tenancy par schéma partagé + `tenant_id` | Schéma PostgreSQL par tenant (django-tenants) ; base par tenant | Simplicité des migrations et de l'exploitation ; isolation garantie par middleware + tests ; volumétrie PME compatible. |
| 003 | Celery + Redis pour l'asynchrone | RQ ; tâches cron ; appels synchrones | Appels IA de 30-60 s et checks réseau hors du cycle HTTP ; retry, files séparées, planification fine (Beat). |
| 004 | API Claude, routage Haiku/Sonnet par tâche | Modèle unique haut de gamme ; LLM auto-hébergé | Adéquation coût/qualité par cas d'usage ; sobriété (Green IT) ; pas de données d'entraînement côté fournisseur en cadre API ; auto-hébergement disproportionné pour le MVP. |
| 005 | Pseudonymisation avant tout appel IA | Envoi du contexte brut | Privacy by design (RGPD), levée du frein d'adoption, surface de risque minimale. |
| 006 | PostgreSQL seul (+ partitionnement) ; pgvector en V2 pour le RAG | Base vectorielle dédiée ; TimescaleDB | Un seul moteur à exploiter ; volumétrie maîtrisée par rollups ; extension vectorielle native suffisante en V2. |
| 007 | Docker Compose sur VPS + Caddy | Kubernetes ; PaaS (Railway) | Coût et sobriété ; maîtrise complète de la chaîne (valeur pédagogique Bloc 3) ; TLS automatique ; K8s surdimensionné. |
| 008 | GitHub Actions : lint → tests → build → scan (Trivy) → deploy | GitLab CI ; Jenkins | Intégré au dépôt GitHub existant ; scan de vulnérabilités cohérent avec le produit ; déploiement SSH simple et auditable. |
| 009 | JWT courts + refresh rotation, RBAC 3 rôles, 2FA TOTP | Sessions serveur ; OAuth externe seul | SPA découplée ; révocation par rotation ; exigence d'exemplarité d'un produit cyber. |
| 010 | Vérifications passives uniquement sur actifs déclarés | Scans actifs de vulnérabilités | Cadre légal (pas de mandat d'intrusion), éthique, positionnement produit ; limite documentée dans les CGU. |
| 013 | Intégration Breachsense (CTI) derrière une interface de provider abstraite | Appel direct depuis les services métier ; polling périodique plutôt que webhook | Inversion de dépendance (changement de fournisseur futur isolé) ; webhook privilégié pour le monitoring continu (hors quota, contrairement au polling qui l'épuiserait). |
| 014 | Non-persistance des secrets renvoyés par Breachsense | Stockage chiffré (comme la pseudonymisation IA ou le TOTP) | Ces secrets appartiennent à des tiers, pas à la plateforme — masquage non réversible dès la normalisation plutôt qu'un chiffrement au repos, quel qu'il soit. |

---

## 6. Sécurité by design

Un produit de cybersécurité doit être exemplaire — la sécurité de la plateforme est un argument produit ET une pièce maîtresse du dossier Bloc 2.

- **Authentification** : JWT de courte durée + rotation des refresh tokens, verrouillage progressif, politique de mots de passe (longueur > complexité, vérification contre listes compromises), 2FA TOTP.
- **Autorisation** : RBAC (admin plateforme / admin tenant / contributeur / lecteur), permissions DRF systématiques, scoping tenant par middleware — testé.
- **Protection applicative** : revue OWASP Top 10 documentée (injections via ORM, XSS via échappement React + CSP, CSRF, SSRF sur les checks sortants — liste d'IP privées bloquée, désérialisation, etc.), rate limiting (Redis) par IP et par tenant, en-têtes de sécurité (HSTS, CSP, X-Frame-Options...).
- **Données** : chiffrement TLS partout, chiffrement au repos des champs sensibles (clés API, correspondances de pseudonymisation) via Fernet, secrets hors du code (variables d'environnement, jamais en clair dans le dépôt).
- **Journalisation** : logs structurés JSON, traçabilité des actions sensibles (connexions, exports, appels IA), rétention définie.
- **Chaîne logicielle** : dépendances épinglées, scan Trivy (images) + pip-audit en CI, Dependabot.

---

## 7. RGPD et conformité de la plateforme elle-même

- **Registre des traitements** tenu (comptes, données de diagnostic, actifs, logs).
- **Base légale** : exécution du contrat (service) ; minimisation des données collectées.
- **Sous-traitants** documentés : hébergeur VPS (UE), fournisseur IA (Anthropic, cadre API sans entraînement sur les données, DPA), service email. Mention dans la politique de confidentialité.
- **Droits des personnes** : export et suppression de compte/tenant (effacement + purge des sauvegardes selon calendrier).
- **Transparence IA** : encart « données transmises » avant chaque appel, IA désactivable par tenant, quotas visibles.
- **Durées de conservation** : résultats de checks bruts 90 jours (agrégats 2 ans), logs 12 mois, correspondances de pseudonymisation à durée de vie courte.

---

## 8. Numérique responsable / Green IT (compétence transversale, validée via Bloc 2 ou 3)

- **Sobriété IA** : routage Haiku (tâches courtes, ~x10 moins coûteux et énergivore) vs Sonnet (génération longue) ; cache des réponses stables ; quotas par tenant ; suivi tokens/coût/estimation CO₂ par cas d'usage — indicateurs restitués dans le back-office.
- **Sobriété infra** : un VPS unique dimensionné au besoin (vs K8s multi-nœuds), hébergeur UE affichant un PUE bas / énergie décarbonée (critère de choix documenté), pas de sur-réplication.
- **Sobriété logicielle** : rollups des séries temporelles (stockage divisé), périodicités de checks raisonnées (pas de sur-vérification), emails texte+HTML légers, SPA optimisée (code splitting, cache).
- **Éco-conception mesurée** : budget de performance frontend (Lighthouse), poids des pages suivi en CI.

---

## 9. Stratégie de tests (Bloc 3)

Pyramide de tests, exécutée en CI à chaque commit :
1. **Unitaires** (pytest) : scoring, moteur de priorisation, parseurs SPF/DMARC, pseudonymisation (propriété : aucune PII ne sort), permissions.
2. **Intégration** (pytest + base éphémère) : API DRF par module, **tests d'étanchéité multi-tenant systématiques**, tâches Celery (mode eager), pipeline IA avec API mockée.
3. **End-to-end** (Playwright) : parcours critiques — inscription→diagnostic→plan d'action ; déclaration d'actif→check→alerte ; génération de document.
4. **Qualité** : couverture cible ≥ 80 % sur le cœur métier, lint (ruff, eslint), typage (mypy sur les services critiques).
Les checks réseau et l'API Claude sont mockés en CI (déterminisme, coût, sobriété) ; un jeu de tests de contrat vérifie périodiquement les intégrations réelles en préproduction.

---

## 10. CI/CD et exploitation (Bloc 3)

**Pipeline GitHub Actions** (fichier unique, étapes bloquantes) :
`lint & typage` → `tests unitaires + intégration` → `build images Docker` → `scan Trivy + pip-audit` → `tests e2e (docker compose éphémère)` → `push registre (GHCR)` → `déploiement` (SSH : pull, migration, redémarrage progressif) → `smoke tests post-déploiement`.

- **Environnements** : dev (local, compose), préproduction (même VPS, stack isolée, sous-domaine), production.
- **Stratégie de branche** : trunk-based simplifié (main protégée, feature branches courtes, PR + CI verte obligatoire).
- **Rollback** : images taguées par SHA, redéploiement du tag précédent en une commande ; migrations rétro-compatibles (expand/contract).
- **Sauvegardes** : dump PostgreSQL quotidien chiffré, externalisé, test de restauration mensuel documenté.
- **Observabilité** : Sentry (erreurs front+back), logs structurés centralisés, healthchecks (`/healthz` web, heartbeat workers/beat), uptime externe sur la plateforme elle-même, tableau de métriques (latence, files Celery, taux d'échec des checks).
- **Documentation d'exploitation** : runbook (démarrage, incident type, restauration), documentation technique versionnée dans le dépôt, journal des MEP.

---

## 11. Phasage (~14 semaines, >10 h/semaine)

| Phase | Semaines | Contenu | Jalon de sortie |
|---|---|---|---|
| 0. Cadrage | S1-S2 | Spécifications détaillées, maquettes (Figma), diagrammes UML/C4/BPMN, ADR 001-010, backlog outillé | Dossier de conception v1 |
| 1. Socle | S3-S5 | Repo, Docker, CI, auth JWT+2FA, tenants, RBAC, back-office minimal | Démo : inscription + espace isolé, pipeline verte |
| 2. Cœur métier | S6-S8 | Référentiel ANSSI, moteur d'évaluation, scoring+radar, plan d'action kanban | Démo : diagnostic complet bout en bout |
| 3. Surveillance | S9-S10 | Actifs, checks (HTTP, SSL, headers, SPF/DKIM/DMARC), historique, alertes, météo IA quotidienne | Démo : météo reçue à heure choisie |
| 4. IA documentaire | S11 | Pipeline pseudonymisation, génération charte, assistant contextuel, quotas | Démo : charte générée + Q/R |
| 5. Durcissement | S12 | Revue OWASP, rate limiting, e2e complets, performance, accessibilité (RGAA de base) | Audit interne documenté |
| 6. Production | S13-S14 | Déploiement rssiasservice.online, monitoring, sauvegardes, runbook, page d'accueil publique | **Plateforme en production** |
| 7. Renseignement sur la menace | S15 | Intégration Breachsense (CTI) : scan de diagnostic, monitoring webhook, back-office quota/pool, enrichissement IA pseudonymisé, section Compromissions | Démo : détection de compromission simulée → alerte → météo/assistant enrichis |

Phase ajoutée après la Phase 6 initialement prévue (extension du périmètre MVP, cadrage §14) — le
phasage à 6 phases restait la trajectoire de certification ; cette 7ᵉ phase documente une évolution
réelle du produit post-MVP, dans le même esprit de traçabilité continue.

La rédaction des dossiers de certification est **continue** : chaque phase alimente directement les pièces (ADR, benchmarks, captures, incidents, métriques). Une revue « dossier » de 1 h est planifiée à la fin de chaque phase.

---

## 12. Traçabilité vers la certification (RNCP38822, référentiel V2026)

| Bloc / exigence | Où le projet y répond |
|---|---|
| **Bloc 1** (porté principalement par le projet Power BI SG) | Ce projet fournit en appui : étude de faisabilité, benchmark concurrentiel (§1.4), modélisation BPMN des processus (parcours diagnostic, pipeline d'alerte), gestion des risques, roadmap et KPI. |
| **Bloc 2 — conception & développement full-stack** | Architecture C4/UML + BPMN, prototype full-stack complet (React + DRF + PostgreSQL), sécurité by design (§6), haute disponibilité raisonnée, documentation, données (modèle, partitionnement, scoring) et pipeline IA. |
| **Bloc 3 — mise en production & évolution** | CI/CD complet (§10), plan de tests automatisés (§9), livraison continue, surveillance du cycle de vie, monitoring/observabilité, documentation technique couvrant sécurité, accessibilité et multilinguisme (i18n préparée, EN en V2), gestion des évolutions (roadmap V2, migrations expand/contract). |
| **Bloc 4 — pilotage d'équipe** | Scénario de passage à l'échelle : constitution d'une équipe V2 (dev front, dev back/DevOps, alternant), fiches de poste, plan de recrutement avec RH, onboarding, rituels agiles, plan de formation, référentiels d'évaluation, inclusion et handicap — adossé à ce produit réel et à sa roadmap. |
| **Transversale anglais** (via Bloc 1 ou 4) | Veille anglophone native au projet : NIS2/ENISA, OWASP, documentation Anthropic, CVE — comptes-rendus de veille en français inclus dans les dossiers. |
| **Transversale numérique responsable** (via Bloc 2 ou 3) | §8 : routage de modèles, quotas, indicateurs tokens/CO₂, sobriété infra et logicielle, éco-conception mesurée. |

---

## 13. Risques projet et mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Périmètre trop ambitieux pour le temps disponible | Retard, dossier incomplet | MVP strict (§3.1), V2 architecturée non codée, revue de périmètre à chaque fin de phase |
| Réticence des utilisateurs vis-à-vis de l'IA | Adoption | Pseudonymisation, transparence, IA optionnelle (§4.5, §7) — transformé en différenciateur |
| Coût des appels IA | Budget | Routage Haiku/Sonnet, cache, quotas, suivi des tokens |
| Faux positifs de la surveillance (alertes intempestives) | Confiance | Seuils de confirmation (3 échecs consécutifs), périodes de maintenance déclarables |
| Aspect légal de la surveillance | Juridique | Actifs déclarés uniquement, checks passifs, engagement de propriété, CGU (ADR-010) |
| Indisponibilité du développeur (aléas alternance) | Planning | Phasage avec jalons démontrables : chaque phase livre un état présentable au jury |

---

## 14. Prochaines étapes immédiates

1. Valider ce cadrage (ajustements éventuels de périmètre).
2. Initialiser le dépôt GitHub (`rssi-as-a-service`) : structure monorepo (`backend/`, `frontend/`, `docs/`, `docs/adr/`), CI squelette, ce document dans `docs/`.
3. Rédiger les ADR 001 à 005 en version complète.
4. Produire les maquettes des 5 écrans clés (dashboard, diagnostic, plan d'action, actifs/météo, génération IA).
5. Démarrer la Phase 1 (socle) avec Claude Code.
