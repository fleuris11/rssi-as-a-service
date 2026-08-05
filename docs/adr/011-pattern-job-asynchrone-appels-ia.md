# ADR 011 — Pattern job asynchrone pour les appels IA

- **Statut** : Adopté ; implémenté en Phase 4 (IA documentaire)
- **Date** : 2026-08-05
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

ADR-003 (Celery + Redis) et ADR-004 (routage Haiku/Sonnet) posent déjà le principe : un appel à
l'API Claude prend 30 à 60 secondes et ne doit **jamais** s'exécuter dans le cycle requête/réponse
HTTP (CLAUDE.md). Restait à décider, pour la Phase 4, **le contrat API concret** entre le frontend
et ces traitements longs, pour les trois cas d'usage du cadrage §3.1 (M4) : génération de la charte
informatique (US-4.1), assistant contextuel (US-4.2), météo enrichie (cas d'usage 3, optionnel).

Le frontend doit pouvoir déclencher l'appel, savoir qu'il est accepté, puis découvrir le résultat
(ou l'échec) sans bloquer l'utilisateur ni maintenir une connexion HTTP ouverte 30 à 60 secondes.

## Options étudiées

1. **Appel HTTP bloquant côté serveur** : la vue DRF déclenche la tâche Celery puis attend son
   résultat via `AsyncResult.get(timeout=...)` avant de répondre. Rejeté : contredit directement
   CLAUDE.md (« jamais dans le cycle requête/réponse HTTP ») — un worker Gunicorn resterait
   immobilisé 30 à 60 secondes par requête, ce qui annule l'intérêt même de Celery et expose la
   plateforme à un épuisement du pool de workers en cas de pic d'usage IA.
2. **Flux temps réel (WebSocket / Server-Sent Events)**, avec affichage incrémental de la réponse
   (utile en particulier pour l'assistant conversationnel). Rejeté pour cette phase : la stack
   actuelle est un WSGI classique (Gunicorn, cadrage §4.1) sans Django Channels ni infrastructure
   ASGI ; l'ajout de cette brique est disproportionné pour le MVP alors que le cadrage précise
   explicitement que le streaming n'est pas requis pour l'assistant (§ mission Phase 4, cas
   d'usage 2 : « streaming non requis »). Option à réévaluer en V2 si l'expérience attendue
   l'exige (réponse de l'assistant affichée mot à mot).
3. **Pattern job asynchrone avec sondage (polling)** : la requête `POST` crée immédiatement une
   ressource `AIJob` en base (statut `pending`), déclenche la tâche Celery correspondante sur la
   file `ai`, et répond `202 Accepted` avec l'identifiant du job. Le frontend interroge ensuite
   `GET /api/v1/ai/jobs/{id}/` à intervalle régulier (2 secondes) jusqu'à un statut terminal
   (`done` ou `failed`).

## Décision

Pattern job asynchrone (option 3), implémenté une fois de façon générique
(`apps.ai_assistant.models.AIJob` + `apps.ai_assistant.views`) et réutilisé par les deux cas
d'usage exposés à l'utilisateur :

- **Génération de document** : `POST /api/v1/ai/documents/` crée le `GeneratedDocument` (statut
  `generating`) et l'`AIJob` associé, déclenche `generate_document_task.delay(job.id)` sur la file
  `ai`, répond `202` avec les deux ressources. Le frontend interroge `GET /ai/jobs/{id}/` puis
  recharge le document une fois `done`.
- **Assistant contextuel** : `POST /api/v1/ai/conversations/{id}/messages/` enregistre
  immédiatement le message de l'utilisateur (opération rapide, aucune raison de la faire attendre)
  et crée l'`AIJob` qui produira la réponse de l'assistant ; même sondage côté frontend.
- **Idempotence** : chaque tâche vérifie le statut courant du job avant de s'exécuter (`PENDING`
  uniquement) — une redélivraison Celery sur un job déjà `done`/`failed` est un no-op, contrairement
  aux checks de `apps.monitoring` où une exécution en double est inoffensive : ici elle produirait
  un document ou un message dupliqué, un vrai bug visible par l'utilisateur.
- **`AIJob.result_ref`** est un pointeur JSON générique (`{"document_id": ...}` ou
  `{"conversation_id": ..., "message_id": ...}`) plutôt qu'un jeu de clés étrangères nullables par
  cas d'usage — chaque cas d'usage ne remplit qu'une forme, un modèle unique évite la duplication
  du modèle `AIJob` par cas d'usage pour un bénéfice de typage marginal.

**Arbitrage explicite — la météo enrichie ne suit pas ce pattern.** Le cas d'usage 3 (reformulation
de la météo quotidienne) n'est pas déclenché par une requête HTTP utilisateur : c'est un
enrichissement optionnel de la tâche Celery existante `send_weather_email_for_tenant`
(`apps.notifications.tasks`, file `emails`), déjà asynchrone et déjà hors du cycle HTTP. Y ajouter
un aller-retour `AIJob` (créer un job, le dispatcher sur la file `ai`, attendre son résultat avant
d'envoyer l'email) aurait introduit une dépendance inter-files superflue pour un appel qui doit de
toute façon rester silencieusement dégradable : `apps.ai_assistant.services.enrich_weather_summary`
est appelée directement (toujours via le point d'entrée unique `ai_assistant/services.py`, donc
sans déroger à CLAUDE.md), capture toute exception et retourne `None` sur le moindre problème
(IA désactivée, quota dépassé, erreur réseau/API) — le template déterministe de la Phase 3 reste
alors le contenu envoyé. C'est la garantie « la météo part toujours » (CLAUDE.md, pièges connus)
qui prime ici sur l'uniformité du pattern.

## Conséquences

**Positives**
- Contrat API unique et prévisible pour le frontend sur les deux cas d'usage interactifs : `202` +
  identifiant de job, puis sondage — pas de connexion longue à maintenir, pas d'infrastructure
  temps réel à opérer.
- L'historique des `AIJob` (tenant, cas d'usage, statut, message d'erreur, horodatages) constitue
  une piste d'audit complémentaire à `AIUsageLog` (qui trace les tokens/coût), utile pour le
  diagnostic des échecs signalés par un utilisateur.
- Le sondage reste léger : réponse JSON de quelques dizaines d'octets toutes les 2 secondes, pour
  une durée de vie de job de 30 à 60 secondes — coût réseau négligeable (cohérent avec la sobriété
  Green IT du cadrage §8, qui porte surtout sur le coût des appels IA eux-mêmes).

**Négatives / points de vigilance**
- Le sondage introduit une latence de perception bornée par l'intervalle choisi (jusqu'à 2
  secondes après la fin réelle du traitement) — jugé acceptable pour des opérations qui durent déjà
  30 à 60 secondes.
- Pas de réponse incrémentale (token par token) pour l'assistant : la réponse apparaît d'un bloc à
  la fin du job. Assumé pour ce MVP (cadrage : « streaming non requis ») ; à réévaluer si l'usage
  réel montre un besoin de retour plus immédiat sur les échanges longs.
- Deux chemins différents pour « appeler l'IA » coexistent dans le code (pattern job pour les cas
  d'usage HTTP, appel direct synchrone pour la météo enrichie) : documenté ici précisément pour que
  ce choix ne soit pas perçu comme une incohérence lors d'une relecture future, et pour que tout
  nouveau cas d'usage IA HTTP suive le pattern job par défaut, sauf justification équivalente à
  celle de la météo.
