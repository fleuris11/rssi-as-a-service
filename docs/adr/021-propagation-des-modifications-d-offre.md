# ADR-021 — Propagation d'une modification d'offre aux clients existants

- **Statut** : accepté
- **Date** : 2026-08-15
- **Phase** : 11 (console d'administration complète)

## Contexte

La phase 11 rend le catalogue d'offres entièrement administrable depuis
l'interface : prix, descriptifs, fonctionnalités incluses et **quotas**
(emplacements de surveillance, analyses mensuelles, utilisateurs).

Une question restait sans réponse : que devient un client déjà abonné quand
le quota de son offre change ? Elle n'est pas théorique. Baisser « Pilotage »
de 3 à 2 emplacements de surveillance touche immédiatement tous les clients
qui y sont abonnés, et rien dans le produit ne disait ce qui devait leur
arriver.

Le modèle de données permet les deux comportements : `Subscription` porte des
surcharges (`override_monitored_assets`, etc.) qui, lorsqu'elles sont
renseignées, priment sur le quota de l'offre.

## Options

### A. Appliquer la modification à tout le monde

Le quota de l'offre fait autorité, sans exception. Simple, prévisible, une
seule valeur à lire.

Conséquence : un client peut se retrouver **au-dessus de son quota** du jour
au lendemain — trois actifs surveillés pour un quota de deux. Il faut alors
décider quoi faire de l'excédent (le désactiver ? le tolérer ?), et aucune
de ces réponses n'est bonne : la première coupe un service sans préavis, la
seconde crée un état incohérent que personne ne sait expliquer au support.

### B. Geler les clients existants (retenue)

À la **baisse** d'un quota, chaque abonnement en cours reçoit une surcharge
figeant son quota actuel. Le nouveau quota ne vaut que pour les clients
créés ensuite. À la **hausse**, aucune surcharge n'est posée : tout le monde
en profite immédiatement.

### C. Demander à chaque modification

L'interface propose les deux comportements au moment de la modification.

## Décision

**Option B.**

Un client a souscrit sur la foi d'un quota annoncé. Le lui reprendre
unilatéralement est une rupture de l'engagement commercial, pas un réglage
d'exploitation — et cela se produirait sans qu'il en soit informé, par un
simple ajustement de catalogue.

L'asymétrie hausse/baisse est volontaire et n'est pas une incohérence : une
hausse ne peut léser personne, une baisse le peut. Le produit ne se protège
donc que dans le sens où il y a quelque chose à protéger.

L'option C a été écartée parce qu'elle transforme chaque modification de
catalogue en décision, y compris les innombrables ajustements sans
conséquence (renommer une offre, corriger un descriptif). Une question posée
trop souvent finit par être répondue sans être lue.

## Conséquences

- `billing.services.update_plan` pose les surcharges **avant** d'écrire le
  nouveau quota, et renvoie la liste des clients gelés.
- `billing.services.plan_impact` calcule l'aperçu **sans rien écrire** : la
  console l'affiche en confirmation, avec le nombre de clients concernés et
  ce qui change pour chacun.
- La confirmation n'apparaît que si une baisse touche réellement des clients.
  Modifier une offre sans abonné, ou à la hausse, reste immédiat.
- Un quota gelé reste modifiable client par client depuis sa fiche : le gel
  est un plancher automatique, pas une décision définitive.
- Passer un quota de `0` (illimité) à une valeur finie compte comme une
  **baisse**, quel que soit le nombre.
- Un changement d'offre (`change_plan`) efface les surcharges : elles
  appartenaient à la négociation précédente. Les conserver ferait suivre
  silencieusement des quotas sur mesure sur une offre standard.

## Ce que cette décision ne couvre pas

Le **prix**. Modifier le tarif d'une offre ne change rien pour les clients en
cours tant qu'aucun fournisseur de paiement n'est branché (ADR-020) : les
encaissements sont saisis à la main. Le jour où un prélèvement automatique
existera, la même question se reposera pour le prix, et devra être tranchée
explicitement — vraisemblablement dans le même sens.
