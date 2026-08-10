# 015 — Modes de fourniture des données CTI et cassettes rejouables

## Contexte

L'ADR-013 pose l'abstraction `BreachIntelligenceProvider` avec deux
implémentations : `BreachsenseProvider` (API réelle) et `NullProvider`
(aucune licence configurée). Le choix entre les deux se faisait sur un
critère simple : `BREACHSENSE_LICENSE_KEY` présente ⇒ appels réels.

Deux besoins apparus en Phase 8A rendent ce critère insuffisant :

1. **La licence réelle est désormais configurée en développement.** Le
   critère « licence présente ⇒ live » signifie donc que le moindre scan
   déclenché en dev — y compris automatiquement, par le signal `post_save`
   sur `monitoring.Asset` (ADR-013 §2) — consomme le quota **partagé par
   toute la plateforme** (1000 requêtes/mois). Le budget peut être épuisé
   par du développement courant, sans que personne ne s'en aperçoive avant
   qu'un client réel ne soit refusé.
2. **Le produit doit être démontré en direct à des prospects.** Une démo
   dépendant d'un appel API en direct est fragile par construction : latence
   variable, panne du fournisseur, quota épuisé, réseau du lieu de la démo —
   autant de façons de rater une vente pour une raison sans rapport avec le
   produit. Et `NullProvider` (aucune donnée) ne démontre rien.

Le besoin est donc : des données **réalistes**, **stables**, **sans réseau**,
qui traversent malgré tout le **vrai** pipeline d'ingestion — sinon la démo
montre autre chose que le produit.

## Options étudiées

**A. Mocker le client HTTP dans un `settings_demo.py` dédié.**
Rejeté : un jeu de settings supplémentaire par usage (dev, démo, CI) se
désynchronise vite du reste, et le mock vivrait dans la configuration plutôt
que derrière l'interface déjà prévue pour ça (ADR-013).

**B. Peupler la base directement avec des `BreachFinding` de démonstration,
sans passer par le pipeline.**
Rejeté seul (mais retenu en complément, voir « Conséquences ») : une
insertion directe contourne normalisation, masquage, chiffrement, dédoublonnage
et ouverture d'alerte. Les données de démo divergeraient silencieusement du
comportement réel, et la démo pourrait montrer un écran impossible en
production.

**C. Une troisième implémentation de provider qui rejoue des réponses
enregistrées ("cassettes"), sélectionnée par un mode explicite.**
Retenu. Le point d'extension existe déjà (l'interface d'ADR-013), les
cassettes sont des réponses **réelles** du fournisseur (donc fidèles), et tout
ce qui est en aval — normalisation, masquage, chiffrement, dédoublonnage,
alertes — reste strictement le code de production.

## Décision

1. **Trois modes explicites**, pilotés par `BREACHSENSE_MODE` :
   - `live` : appels réels (consomme le quota) ;
   - `replay` : `ReplayProvider`, sert les cassettes de
     `apps/threat_intelligence/tests/fixtures/breachsense/`, **zéro appel
     réseau** ;
   - `null` : `NullProvider` (comportement d'ADR-013 inchangé).

2. **Le défaut (`auto`) ne bascule JAMAIS en `live`**, même lorsqu'une licence
   est configurée : `replay` si des cassettes existent, sinon `null`. C'est le
   cœur de cette décision — **disposer d'une licence est une capacité, pas une
   instruction de la dépenser**. Passer en `live` doit être un acte délibéré
   (variable d'environnement), jamais un effet de bord de la configuration.
   La suite de tests force `null` par défaut (conftest racine), pour que le
   résultat des tests ne dépende jamais des cassettes committées.

3. **Une cassette ne contient jamais de secret en clair.** L'ADR-014
   s'applique aux fixtures exactement comme à la base : la commande
   d'enregistrement passe chaque payload par `normalizer.mask_payload`
   **avant** écriture. Une cassette est donc committable sans risque, et le
   fichier porte lui-même un marqueur `"secrets_masked": true` pour quiconque
   l'ouvre sans avoir lu cet ADR.

4. **Une seule commande appelle délibérément l'API réelle** :
   `record_breachsense_cassette --domain X --confirm-live-call`. Elle
   instancie `BreachsenseProvider` **directement**, sans passer par
   `get_provider()` — c'est précisément son rôle de contourner le mode
   configuré, et le flag obligatoire garantit qu'aucune cassette ne
   s'enregistre comme effet de bord d'autre chose.

5. **Un rejeu ne consomme aucun quota** : `ReplayProvider` renvoie
   `requests_consumed=0`, pour que `QuotaManager`/`BreachIntelligenceUsage` ne
   comptabilisent pas une dépense qui n'a pas eu lieu.

## Conséquences

- Le développement courant et la CI n'ont plus aucun chemin par lequel un
  appel réel peut partir par accident — le risque principal identifié en
  Phase 8A est fermé par construction, pas par discipline.
- La démo client ne dépend plus du réseau ni du fournisseur. Elle s'appuie
  sur deux briques complémentaires : `seed_demo_tenant` (option B, assumée
  ici en complément et non en remplacement — elle crée ses findings **via**
  `services.ingest_raw_findings`, donc à travers le pipeline réel) et le mode
  `replay` (qui rend un « Lancer un scan » démontrable en direct).
- Les cassettes sont des fixtures de test au même titre que les payloads
  simulés existants : elles vivent dans `tests/fixtures/`, sont versionnées,
  et se rafraîchissent par une commande explicite plutôt qu'à la main.
- Le mode réellement actif est exposé par `providers.resolve_mode()` — un
  opérateur peut le constater plutôt que le déduire de la configuration.
- **Risque résiduel accepté** : une cassette vieillit (le schéma réel de
  Breachsense peut dériver). Elle reste fidèle au jour de son enregistrement,
  pas au-delà — le smoke test avec la licence réelle (reste-à-faire déjà noté
  en Phase 7) demeure la seule vérification du schéma courant, et le
  ré-enregistrement d'une cassette est le moment naturel pour le faire.
