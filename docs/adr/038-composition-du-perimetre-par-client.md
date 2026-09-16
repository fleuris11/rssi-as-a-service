# ADR-038 — Composer le périmètre d'un client, et ce qu'on lui montre

- **Date** : 16/09/2026
- **Statut** : acceptée
- **Contexte** : V2-8, modularité par client

## Contexte

`Subscription.override_features` existe depuis la phase 10 : la liste des
fonctionnalités d'un client peut être fixée indépendamment de son offre, et la
résolution fonctionne (`effective_features` prend la surcharge quand elle
existe, sinon l'offre).

Aucune interface ne la réglait. Dire « ce client voit seulement Veille et
Documents » demandait d'écrire en base — donc un accès au serveur, aucune
trace, et aucun moyen de savoir ensuite ce qui déviait de l'offre.

Trois questions se posaient, et deux avaient une réponse qui semblait évidente
mais était fausse.

## Décision 1 — masquer ce qui a été retiré, désactiver ce qui est hors offre

La règle du projet est « désactivé, jamais masqué » : une fonctionnalité hors
offre reste visible, grisée, avec l'offre qui la débloque. Elle a été posée
pour un usage commercial — le client doit savoir que le produit sait le faire.

**Cette règle ne s'applique pas à un périmètre réduit volontairement.** Montrer
à un client ce qu'on vient de lui retirer n'est pas un levier commercial :
c'est une invitation à demander ce qu'on a décidé de ne pas lui donner, et
souvent une négociation déjà tranchée. L'interface distingue donc la CAUSE de
l'absence, pas seulement l'absence :

| Cause | Ce que le client voit | Pourquoi |
|---|---|---|
| Non comprise dans l'offre (`source: "plan"`) | Élément **désactivé**, infobulle nommant l'offre | Levier commercial (règle historique) |
| Retirée pour ce client (`source: "override"`) | **Rien** : l'entrée sort du menu, la garde ne rend rien | On ne propose pas ce qu'on a retiré |

La garde serveur ne change pas : elle refuse dans les deux cas. Le masquage est
une décision d'affichage, jamais une sécurité.

**Conséquence assumée** : un client dont on a retiré une fonctionnalité ne peut
plus la demander depuis son espace (l'encart « Demander cette fonctionnalité »
disparaît avec elle). C'est voulu — la demande passe par son interlocuteur.

## Décision 2 — les dépendances sont de deux natures, et aucune n'est entre fonctionnalités

La question posée était « retirer le diagnostic doit-il retirer le plan
d'action ? ». En établissant la carte, le constat est que **les neuf clés du
registre ne dépendent d'aucune autre** : elles portent des capacités greffées
sur des écrans qui, eux, ne sont jamais conditionnés (Exposition,
Compromissions, Documents, Veille). `DEPEND_DE` est donc **vide**, et ce vide
est vérifié, pas oublié.

Les dépendances réelles sont ailleurs :

1. **Fonctionnalité → quota** (`QUOTA_REQUIS`). Activer « Comptes surveillés »
   chez un client dont le quota vaut zéro produit un écran dont chaque action
   est refusée. La composition est refusée, avec la phrase qui dit quoi faire :
   relever le quota, ou retirer la fonctionnalité. Même chose pour la
   surveillance en temps réel et les emplacements.
2. **Fonctionnalité → écrans dérivés** (`ECRANS_DERIVES`). Le plan d'action est
   *produit* par la clôture d'un diagnostic, et les résultats en sont la
   lecture. Retirer « Diagnostic de maturité » retire donc aussi « Résultats »
   et « Plan d'action » du menu : les laisser afficherait deux écrans vides
   dont le message invite à faire un diagnostic auquel le client n'a pas droit.
   Les données déjà produites ne sont pas détruites — elles redeviennent
   visibles si la fonctionnalité revient.

Un écran retiré reste **refusé par le serveur** indépendamment du menu : le
masquage ne protège rien, la garde protège.

## Décision 3 — l'état hérité est toujours affiché à côté de l'état effectif

Une surcharge invisible est une dette : six mois plus tard, personne ne sait
plus pourquoi ce client a un périmètre différent, ni s'il suit encore son
offre. La console affiche donc, pour chaque fonctionnalité, ce que l'offre
donne ET ce que le client a, avec la mention de l'écart (« ajoutée », «
retirée »), plus un bouton « revenir à l'offre » qui efface la surcharge.

Composer une liste identique à l'offre **reste** une surcharge : c'est une
décision, et le jour où l'offre change, ce client ne doit pas suivre sans
qu'on l'ait voulu.

## Conséquences

- Chaque composition est tracée dans le journal d'audit (`features_composed`,
  `features_reset`) avec l'état avant et après, l'auteur et l'horodatage.
- Un changement d'offre **efface** la composition (comportement existant des
  surcharges de quota) : la négociation appartenait à l'offre précédente.
- La console peut afficher le menu tel que le client le voit, sans se
  connecter à son compte : le menu se calcule à partir de la même
  configuration de navigation et du périmètre résolu par le serveur. Le
  principe reste celui déjà décidé — un administrateur plateforme n'entre pas
  dans un espace client.
- Le registre porte désormais trois tables déclaratives (`DEPEND_DE`,
  `QUOTA_REQUIS`, `ECRANS_DERIVES`). Ajouter une clé sans se poser la question
  de ses dépendances reste possible ; un test épingle que chaque clé citée
  dans ces tables existe réellement dans le registre.
