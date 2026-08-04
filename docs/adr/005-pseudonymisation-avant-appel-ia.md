# ADR 005 — Pseudonymisation avant tout appel IA

- **Statut** : Adopté ; implémentation prévue en Phase 4 (IA documentaire)
- **Date** : 2026-08-04
- **Décideur** : développeur unique (freelance, support RNCP38822)

## Contexte

La plateforme envoie à un fournisseur tiers (API Anthropic) des données dérivées du contexte
métier de chaque tenant (secteur, effectif, réponses agrégées au diagnostic, informations utiles
à la génération documentaire). Certaines de ces données peuvent, directement ou par recoupement,
identifier l'entreprise ou des personnes (raison sociale, noms de dirigeants, domaines, adresses
IP, emails).

Deux contraintes fortes s'appliquent : le RGPD (minimisation des données transmises à un
sous-traitant, cadrage §7) et l'adoption produit — la cible (dirigeants de TPE/PME, cadrage §1.4)
est explicitement identifiée comme réticente à l'idée qu'une IA externe traite des données
d'entreprise sensibles (cadrage §13, risque « Réticence des utilisateurs vis-à-vis de l'IA »). La
transparence et la minimisation sont donc autant une exigence de conformité qu'un argument produit.

## Options étudiées

1. **Envoi du contexte brut** (raison sociale, noms, domaines réels) à l'API. Solution la plus
   simple techniquement, mais expose des données identifiantes à un tiers sans nécessité — contraire
   au principe de minimisation RGPD, et au frein d'adoption identifié. Écarté.
2. **Anonymisation irréversible** (suppression pure des identifiants, sans mécanisme de
   correspondance). Réduit le risque au minimum, mais rend impossible la ré-injection des
   identifiants réels dans la réponse (ex. une charte informatique doit mentionner le nom réel de
   l'entreprise) — casserait l'utilisabilité du document généré. Écarté.
3. **Pseudonymisation réversible** : remplacement des identifiants réels par des placeholders avant
   l'appel, table de correspondance conservée uniquement côté serveur, ré-injection des identifiants
   réels dans la réponse reçue.

## Décision

Pseudonymisation réversible systématique, appliquée par une couche dédiée dans
`ai_assistant/services.py`, **avant** tout appel à l'API Claude (voir ADR-004) — jamais après, et
jamais contournable depuis un autre point du code (contrainte déjà actée dans CLAUDE.md : « aucun
appel direct à l'API Anthropic ailleurs dans le code »).

Concrètement (cadrage §4.5) :
1. Construction du contexte **minimal** nécessaire au cas d'usage (jamais de PII brute par
   défaut : secteur, effectif, réponses agrégées).
2. Remplacement des identifiants réels restants (raison sociale, noms, domaines, IP) par des
   placeholders ; la table de correspondance est conservée **côté serveur uniquement**, avec une
   durée de vie courte (cadrage §7), et n'est jamais transmise au fournisseur IA.
3. Appel API sur le contexte pseudonymisé.
4. Ré-injection des identifiants réels dans la réponse reçue, avant présentation à l'utilisateur.
5. Validation humaine obligatoire avant tout export de document généré (US-4.1).

Chaque appel est par ailleurs journalisé (tenant, cas d'usage, volume de tokens, coût — cadrage
§4.5/§8), sans jamais inclure de PII dans les logs (CLAUDE.md : « ne jamais stocker de données
personnelles dans les logs ni les envoyer à Sentry »).

## Conséquences

**Positives**
- Surface de risque minimale en cas d'incident côté fournisseur : les données réellement
  transmises à l'API ne permettent pas, seules, d'identifier l'entreprise ou ses collaborateurs.
- Conformité RGPD par construction (privacy by design) plutôt que par contrôle a posteriori.
- Argument de confiance direct pour l'adoption produit (transparence affichée à l'utilisateur avant
  chaque appel IA, US-4.3), qui transforme un risque identifié (cadrage §13) en différenciateur
  commercial (cadrage §1.4).

**Négatives / points de vigilance**
- Complexité supplémentaire dans le pipeline IA : un défaut dans la logique de remplacement ou de
  ré-injection pourrait laisser fuiter un identifiant réel vers le fournisseur, ou à l'inverse
  renvoyer un placeholder non résolu à l'utilisateur. Le plan de tests (cadrage §9) prévoit
  explicitement un test de propriété dédié — « aucune PII ne sort » — à écrire avec l'implémentation
  en Phase 4, en plus des tests unitaires classiques du module de pseudonymisation.
- La table de correspondance pseudonyme ↔ identifiant réel est elle-même une donnée sensible : sa
  durée de vie doit rester courte et son accès restreint, au même titre que les autres données
  sensibles chiffrées au repos (clés API, cadrage §6).
- Légère latence additionnelle liée au pré/post-traitement, négligeable au regard du temps d'appel
  API lui-même (30 à 60 secondes selon le cas d'usage, ADR-003).
