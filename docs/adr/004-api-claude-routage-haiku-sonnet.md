# ADR 004 — API Claude avec routage Haiku/Sonnet par tâche

- **Statut** : Adopté ; implémentation prévue en Phase 4 (IA documentaire)
- **Date** : 2026-08-04
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

La plateforme a deux usages de génération de texte par IA, de nature très différente :
- des **synthèses courtes et fréquentes** : la météo cyber quotidienne (un paragraphe, envoyée à
  chaque tenant actif chaque jour) et de la classification/extraction légère ;
- de la **génération documentaire longue et ponctuelle** : la charte informatique personnalisée,
  rédigée à partir du contexte de l'entreprise, avec un enjeu de qualité rédactionnelle plus élevé
  (le document est ensuite validé par l'utilisateur et exporté).

Le cadrage impose une exigence transversale de sobriété numérique (Green IT, §8) : « routage
Haiku (tâches courtes) vs Sonnet (génération longue) », et le modèle économique du projet
(freelance, TPE/PME à budget contraint) impose une maîtrise fine des coûts d'inférence, qui
croissent avec le volume d'appels (météo quotidienne = un appel par tenant actif, chaque jour).

## Options étudiées

1. **Un seul modèle haut de gamme pour tout** (Sonnet uniquement). Simplicité d'implémentation
   maximale, mais coût et empreinte énergétique disproportionnés pour un usage aussi fréquent que la
   météo quotidienne — contraire à l'exigence Green IT du cadrage. Écarté.
2. **LLM auto-hébergé** (poids ouverts, type Llama/Mistral, hébergé sur l'infrastructure du
   projet). Écarté pour le MVP : nécessiterait un GPU dédié (coût et complexité d'exploitation
   disproportionnés pour un VPS unique opéré par une seule personne), et une maintenance de modèle
   (mises à jour, qualité) hors du cœur de métier du produit. Reste une option de réévaluation en V2
   si le volume d'appels et la maîtrise des coûts le justifient.
3. **API Claude, routage par cas d'usage** entre modèles de tailles différentes selon la complexité
   de la tâche.

## Décision

API Anthropic (Claude), avec un **routage explicite par cas d'usage** :
- **Haiku** par défaut pour les tâches courtes et fréquentes (météo quotidienne, classification,
  extraction) ;
- **Sonnet** réservé aux tâches qui le justifient (génération documentaire longue, ex. charte
  informatique).

Conformément à CLAUDE.md, **tout** appel à l'API Claude passe exclusivement par
`ai_assistant/services.py` — aucun appel direct à l'API Anthropic ailleurs dans le code. Ce point
d'entrée unique applique, dans l'ordre : pseudonymisation du contexte (voir ADR-005), appel API,
ré-injection des identifiants réels, journalisation (tenant, cas d'usage, volume de tokens, coût
estimé). Aucun appel IA ne s'exécute dans le cycle requête/réponse HTTP : il est systématiquement
déclenché via une tâche Celery de la file `ai` (voir ADR-003).

## Conséquences

**Positives**
- Coût et empreinte réduits sur l'usage le plus fréquent (météo quotidienne, potentiellement un
  appel par tenant actif et par jour) : Haiku est environ dix fois moins coûteux et énergivore que
  Sonnet pour ce type de tâche (cadrage §8), ce qui rend le modèle économique du produit tenable à
  l'échelle.
- Qualité rédactionnelle adaptée à l'enjeu : Sonnet là où le document est conservé, exporté et
  engage la crédibilité du produit (charte informatique) ; Haiku là où la brièveté et la régularité
  priment.
- Passer par une API managée (plutôt que l'auto-hébergement) évite au projet — porté par une seule
  personne — la responsabilité d'opérer et de maintenir à jour un modèle de langage.
- Le point d'entrée unique (`ai_assistant/services.py`) limite la surface de code qui connaît le
  fournisseur IA : une migration future vers un autre fournisseur ou modèle resterait localisée à
  cette couche.

**Négatives / points de vigilance**
- Dépendance à un fournisseur externe (disponibilité, tarifs, évolution des modèles) : mitigée par
  la centralisation de l'intégration dans une seule couche de service, et par le cadre contractuel
  API (pas d'entraînement des modèles sur les données transmises, cf. cadrage §7).
- Le coût reste variable et proportionnel à l'usage : nécessite des quotas de tokens par tenant et
  un suivi coût/tokens visible en back-office (cadrage §8), à implémenter avec la fonctionnalité en
  Phase 4 — non encore développé à ce stade (Phase 1).
- Le choix Haiku/Sonnet par défaut doit rester révisable par tâche à mesure que de nouveaux cas
  d'usage apparaissent (ex. assistant conversationnel, US-4.2) : la décision de routage pour chaque
  nouveau cas d'usage doit être documentée dans le code du point d'entrée, pas seulement dans cet
  ADR.
