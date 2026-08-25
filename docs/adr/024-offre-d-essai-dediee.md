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
| Veille | 1 sur 15 | **non** | 15 essais possibles, mais l'inscrit ne peut pas faire le diagnostic |
| Souverain | 5 sur 15 | oui | sur devis : n'a pas de sens pour un essai |

La phase 10 a basculé l'essai de « Pilotage » vers « Veille » pour régler le
premier problème. Elle a créé le second, et personne ne l'a vu pendant deux
semaines : **un prospect s'inscrivait pour ne pas pouvoir faire la première
chose qu'on lui avait promise.**

Aucun test unitaire ne pouvait le détecter — chacun déclare l'offre dont il a
besoin, c'est même une bonne pratique posée en phase 10 après un incident
inverse. Seul un parcours de bout en bout partant d'une inscription réelle
l'a révélé, et seulement une fois la CI capable d'exécuter ces parcours.

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

Réglerait le symptôme en une ligne. Mais le diagnostic est ce qui distingue
« Pilotage » (249 €) de « Veille » (89 €) : le donner à 89 € supprime la
raison de monter d'offre. On corrigerait un défaut produit en détruisant le
modèle commercial.

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

## Ce que cet épisode dit du dispositif de test

C'est le **deuxième** défaut de cette nature : un réglage commercial juste au
regard d'une contrainte, faux au regard d'une autre, invisible pour toute la
suite unitaire. Le premier était la saturation du pool (phase 10).

La leçon n'est pas « écrire plus de tests unitaires » — ils auraient continué
à passer. C'est qu'**un parcours partant d'une inscription réelle est le seul
qui traverse la configuration commerciale**, et qu'une CI incapable de les
exécuter ne protège pas de cette classe de défaut. La course aux migrations
qui empêchait la pile de démarrer en intégration continue (corrigée le même
jour) coûtait donc bien plus que ce qu'elle affichait.
