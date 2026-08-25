# ADR-024 — L'essai est une offre à part

- **Statut** : accepté
- **Date** : 2026-08-25
- **Contexte** : prolonge ADR-013 (licence CTI partagée) et ADR-019 (offres et
  ressource rare)

## Contexte

L'essai gratuit de 14 jours démarrait sur une offre du catalogue, désignée par
un réglage (`BILLING_DEFAULT_TRIAL_PLAN_CODE`). Aucune des trois offres ne
convient, et **pour des raisons opposées** :

| Offre | Emplacements engagés | Diagnostic ANSSI | Conséquence |
|---|---|---|---|
| Pilotage | 3 sur 15 | oui | 5 essais possibles au total, **zéro** une fois le jeu de démonstration chargé (13/15 déjà engagés) |
| Veille | 1 sur 15 | **non**, d'après le catalogue | 15 essais possibles, mais l'essai porte une offre qui exclut le diagnostic |
| Souverain | 5 sur 15 | oui | sur devis : n'a pas de sens pour un essai |

La phase 10 a basculé l'essai de « Pilotage » vers « Veille » pour régler le
premier problème, sans voir le second.

### Correction d'une erreur d'analyse

Cet ADR a d'abord été rédigé en affirmant qu'un prospect **ne pouvait pas**
faire le diagnostic pendant son essai. **C'est faux, et il faut le dire.**

Vérification faite, `anssi_assessment` est une clé **déclarée dans le registre
des fonctionnalités et appliquée nulle part** : aucune vue, aucun sérialiseur,
aucun composant ne la contrôle. Un client sur « Veille » accède donc
aujourd'hui au diagnostic, essai ou pas.

Ce n'est pas une bonne nouvelle, c'est un défaut plus large — voir plus bas.

Il n'y avait donc **aucune panne visible** à réparer. Ce qui reste vrai :

- l'essai porte une offre dont le catalogue dit qu'elle **n'inclut pas** le
  diagnostic ;
- le jour où cette garde sera posée — et elle doit l'être, c'est la
  différence vendue entre 89 € et 249 € — **l'essai cassera**, sans que rien
  dans le code ne change ;
- l'offre d'essai est donc le **préalable** à l'application des gardes, pas la
  réparation d'une panne.

## Le raisonnement

Les deux contraintes portent sur des choses différentes :

- **Les emplacements de surveillance sont rares.** Quinze pour la plateforme
  entière (ADR-013). Chaque essai en consomme réellement.
- **Les fonctionnalités ne coûtent rien.** Activer le diagnostic ANSSI pour un
  compte n'enlève rien à personne.

Les traiter comme un seul curseur — « quelle offre du catalogue ? » — force à
choisir entre une plateforme saturée et un essai qui ne montre pas le produit.
Ce sont deux réglages, pas un.

## Options

### A. Ajouter le diagnostic à « Veille »

Réglerait la question en une ligne. Mais le diagnostic est ce qui distingue
« Pilotage » (249 €) de « Veille » (89 €) : le donner à 89 € supprime la raison
de monter d'offre. Ce serait entériner la situation actuelle — où la garde
n'est pas appliquée — au lieu de la corriger.

### B. Revenir à « Pilotage » et augmenter le palier de licence

Résout tout, contre de l'argent qu'on n'a pas aujourd'hui. Reste la piste du
jour où le produit finance son palier supérieur.

### C. Une offre d'essai dédiée (retenue)

Un emplacement — le coût d'un essai sur la ressource rare — et les
fonctionnalités qui donnent envie de payer.

## Décision

**Option C.** Une offre `essai`, avec un statut nouveau : `internal`,
c'est-à-dire **attribuable mais jamais affichée au catalogue public**.

| | |
|---|---|
| Emplacements | 1 (comme « Veille ») |
| Diagnostic ANSSI, plan d'action, génération documentaire, assistant | oui |
| Révélation de secret en clair | **non** |
| Visible sur la grille tarifaire | non |
| Prix | néant : elle n'est pas vendue, elle est attribuée |

Un statut nouveau plutôt que le repli sur « Brouillon » : dire « brouillon »
d'une offre réellement attribuée à de vrais essais serait faux, et un statut
qui ment finit par tromper la personne qui administre le catalogue.

**`secret_reveal` reste hors de l'essai.** Afficher en clair un mot de passe
réellement fuité est l'action la plus sensible du produit (ADR-014). Le refus
nomme l'offre qui la débloque : c'est un argument de vente, pas une porte
close sans explication.

## Conséquences

- Quinze essais simultanés possibles au lieu de cinq, sans rien retirer au
  prospect.
- La grille tarifaire publique est inchangée : trois offres, comme avant.
- Le statut `internal` est réutilisable — offre partenaire, tarif négocié,
  compte de démonstration — sans nouvelle décision d'architecture.
- L'essai devient modifiable depuis la console (fonctionnalités, quotas,
  offre par défaut) sans redéploiement.

## Le vrai défaut découvert au passage

En vérifiant si « Veille » bloquait réellement le diagnostic, un problème plus
sérieux est apparu : **neuf fonctionnalités sont déclarées au registre, trois
seulement sont appliquées.**

| Appliquée | Déclarée mais sans garde |
|---|---|
| `exposure_synthesis`, `secret_reveal`, `realtime_monitoring` | `assistant`, `pdf_export`, `reuse_correlation`, `anssi_assessment`, `charter_generation`, `extended_history` |

Autrement dit : **un client « Veille » à 89 € obtient aujourd'hui l'essentiel
de ce qui est vendu 249 € au titre de « Pilotage ».** Ce n'est pas une panne —
rien ne casse, tout le monde a tout — c'est une fuite commerciale, invisible
par construction : aucun test ne peut échouer sur une garde qui n'existe pas,
et aucun client ne se plaindra d'avoir trop de fonctionnalités.

C'est le mode de défaillance le plus discret de ce projet : le registre des
fonctionnalités **donne l'apparence** d'un contrôle d'accès. Lire
`features.py` laisse croire que les offres sont appliquées. Seule la recherche
des points d'usage montre que six clés sur neuf ne sont lues nulle part.

La suite est traitée hors de cet ADR (voir `docs/deploiement_production.md`
§10) : poser les six gardes manquantes est un travail à part entière, qui
touche l'interface autant que l'API, et qui doit être fait **après** que
l'essai a cessé de dépendre d'une offre du catalogue — sans quoi le poser
casserait l'essai. C'est précisément ce que cet ADR met en place.
