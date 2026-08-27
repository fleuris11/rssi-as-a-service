# ADR-025 — Retrait de la clé « historique étendu »

- **Statut** : accepté
- **Date** : 2026-08-26
- **Contexte** : prolonge ADR-019 (registre des fonctionnalités) et prépare la
  pose des gardes manquantes (phase 12)

## Contexte

Le registre des fonctionnalités déclare neuf clés. Six n'étaient appliquées
nulle part (voir ADR-024). Avant de poser les gardes correspondantes, chaque
clé devait recevoir une définition vérifiable : **une garde ne peut pas
s'appuyer sur une notion floue.**

Cinq des six se sont laissées définir sans difficulté. La sixième,
`extended_history`, non.

Sa promesse au catalogue : « Conservez et consultez l'historique complet de
vos analyses **au-delà de la période standard**. » Elle n'était vendue que par
l'offre « Souverain ».

## Le problème n'est pas celui qu'on attendait

On redoutait une notion **inséparable d'un quota** — auquel cas la garde et le
quota `monthly_scans` se seraient marché dessus, comme en phase 11.

Ce n'est pas le cas : `monthly_scans` compte des analyses consommées dans le
mois, il ne tronque aucun historique. Les deux notions ne se croisent pas.

Le problème est plus embarrassant : **il n'y a aucune période standard.**
Recherche faite dans tout le dépôt :

| Ce qu'on cherchait | Ce qui existe |
|---|---|
| Une rétention par client | Aucune. Les trois réglages de rétention (secrets, audit de révélation, corbeille) sont des réglages **plateforme**, identiques pour tous, réglés en console par l'exploitant. |
| Une purge de l'historique métier | Aucune. La purge de phase 8C efface le **secret** d'une fuite, jamais la fuite : constats, statuts et dates restent indéfiniment. |
| Une fenêtre d'historique paramétrable | Aucune. La seule fenêtre du produit est le taux de disponibilité sur 24 h, en dur dans `monitoring.services.compute_uptime_percentage`, la même pour toutes les offres. |
| Un rollup de série temporelle | Aucun. C'est une cible Green IT, pas une fonctionnalité livrée. |

Autrement dit : **tout le monde a déjà l'historique complet, pour toujours.**
« Étendu » ne se distingue de rien.

## Ce qui a tranché

Deux raisons, l'une commerciale, l'autre technique.

**Un client « Souverain » paie pour une fonctionnalité inexistante.** Et la
question « c'est quoi, l'historique étendu ? » n'a pas de réponse en
rendez-vous. Ce n'est pas un défaut de code : c'est une ligne vendue qui ne
correspond à rien.

**La définir maintenant contredirait une règle qu'on ne veut pas plier.** Une
garde d'historique consisterait à **masquer à un client des données que son
propre compte détient déjà**. Or la règle posée pour les cinq autres gardes
est explicite : un client qui perd une fonctionnalité **garde l'accès en
lecture** à ce qu'il a produit — on ne prend jamais ses données en otage
(ADR-019). Les deux ne tiennent pas ensemble.

## Options

### A. Inventer une définition et poser la garde

Par exemple : « les offres de base ne voient que 90 jours de constats ».
Rejetée. Il faudrait **retirer** de l'affichage des données déjà présentes
chez des clients existants, pour créer artificiellement une rareté que le
produit ne connaît pas. C'est une dégradation vendue comme une option.

### B. Laisser la clé déclarée et non gardée

C'est l'état actuel, et c'est ce que la phase 12 corrige précisément : une clé
déclarée mais appliquée nulle part **donne l'apparence** d'un contrôle d'accès.
Lire le registre laisse croire que l'offre est appliquée.

### C. Retirer la clé du registre (retenue)

## Décision

**Option C.** `extended_history` est retirée :

- du registre (`apps/billing/features.py`) ;
- des fonctionnalités de l'offre « Souverain » en base (migration `0005`) ;
- de la description publique de « Souverain », qui la mentionnait en toutes
  lettres.

Le retrait est **sûr par construction** : `features.sanitize()` ignore déjà les
clés inconnues (ADR-019). Une base qui porterait encore la chaîne ne casserait
rien. La migration nettoie quand même la donnée, pour qu'une lecture directe
de la table ne laisse pas croire que la fonctionnalité existe.

## Conséquences

- La grille tarifaire publique cesse de promettre ce que le produit ne fait
  pas. « Souverain » garde ses quotas paramétrables, ses utilisateurs
  illimités et l'accompagnement — qui, eux, existent.
- Il n'y a **rien à retirer à personne** : aucun client n'avait accès à quoi
  que ce soit au titre de cette clé, puisqu'elle n'était lue nulle part.
- Le registre retrouve la propriété que la phase 12 lui rend : **toute clé
  déclarée est appliquée quelque part.** C'est ce qu'un test structurel
  vérifie désormais — et il aurait échoué sur `extended_history` sans ce
  retrait, ce qui est exactement le comportement voulu.

## Réversibilité

La clé reviendra le jour où une **rétention différenciée par offre** sera
réellement implémentée — c'est-à-dire quand il y aura quelque chose à étendre.
Il faudra alors, dans cet ordre : une rétention de base appliquée à tous, puis
un paramètre par offre, puis la clé et sa garde. Poser la clé avant la
rétention, c'est ce qui a produit cette situation.
