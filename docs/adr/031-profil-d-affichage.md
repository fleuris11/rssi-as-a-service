# ADR-031 — Un profil d'affichage, qui ne change pas les données

- **Statut** : accepté
- **Date** : 2026-09-10
- **Contexte** : V2-5, partie A. S'ajoute aux rôles existants (US-1.2,
  administrateur / contributeur / lecteur) sans les toucher.

## Contexte

Le produit s'adresse à deux lecteurs qui regardent les mêmes écrans : le
dirigeant de la PME, et la personne qui gère son informatique — salarié ou
prestataire. Ils n'ont pas besoin de la même lecture. « En-tête
`Strict-Transport-Security` absent » ne dit rien au premier ; « votre site ne
demande pas au navigateur de rester en connexion sécurisée » fait perdre du
temps au second, qui sait déjà.

Jusqu'ici le produit tranchait pour tout le monde, et il tranchait en faveur
du dirigeant : vocabulaire vulgarisé partout, détails techniques absents.
Conséquence, le prestataire devait aller chercher dans l'API ce que l'écran ne
lui montrait pas.

## Décision 1 — Un réglage porté par l'utilisateur, pas par l'entreprise

`User.display_profile` vaut `executive` ou `technical`, défaut `executive`.

Sur l'utilisateur et non sur le tenant : dans une même PME, le dirigeant et
son prestataire ont chacun un compte, et un réglage d'entreprise obligerait
l'un des deux à subir la lecture de l'autre. Sur l'utilisateur *plateforme* et
non sur l'appartenance (`Membership`) : quelqu'un qui suit trois entreprises
ne change pas de cerveau en changeant de client.

Le défaut est `executive` parce que c'est le lecteur que le produit vise en
premier, et parce que c'est le réglage le moins risqué : on ne noie personne
sous du jargon qu'il n'a pas demandé.

## Décision 2 — Ce n'est pas un rôle, et cela se vérifie

Les droits restent portés par `Membership.role`. Le profil d'affichage n'est
lu par aucune permission, aucune garde, aucun service.

Deux tests le tiennent : un lecteur en profil technique reste refusé au
démarrage d'un diagnostic ; un administrateur en profil dirigeant garde ses
droits d'administrateur. Sans eux, la confusion serait naturelle — les deux
notions sont des attributs d'utilisateur qui influent sur ce qu'on voit.

## Décision 3 — Le serveur ignore le profil. Complètement.

**Aucune réponse d'API ne dépend du profil d'affichage.** Le réglage est
persisté côté serveur (il suit la personne d'un poste à l'autre), et appliqué
uniquement à l'affichage, côté client.

C'est la traduction technique du point 3 de la consigne : *« le contenu ne
change jamais — seule sa présentation change. Un même fait doit rester le même
fait. »* Une règle de rédaction se contourne ; une architecture où le serveur
ne connaît pas le profil au moment de sérialiser ne se contourne pas par
distraction.

Un test paramétré compare, pour quatre endpoints représentatifs, la charge
utile renvoyée dans les deux profils et exige qu'elles soient identiques —
sérialisées et triées, pour que l'écart, s'il apparaît un jour, se lise dans
le diff.

### Alternative écartée : adapter la réponse au profil

C'était tentant : le serveur sait déjà rédiger (les messages d'alerte, la
météo). On aurait pu renvoyer un `label` vulgarisé ou technique selon le
lecteur.

Rejeté pour trois raisons. D'abord, deux versions d'un même fait finissent par
diverger — on corrige la formulation dirigeant et on oublie l'autre. Ensuite,
un cache HTTP ou applicatif devient dépendant de l'utilisateur, pas seulement
du tenant. Enfin et surtout : dès que la réponse dépend du profil, plus rien
ne garantit que le dirigeant *peut* voir ce que voit le technicien. La
garantie « même fait » devient une intention, alors qu'ici elle est une
propriété.

## Décision 4 — Trois primitives d'affichage, pas des conditions éparpillées

Le frontend expose `useDisplayProfile()` et trois composants :

| Composant | En profil dirigeant | En profil technique |
|---|---|---|
| `TechnicalDetail` | replié, ouvrable d'un clic | déplié par défaut |
| `Term` | traduction devant, terme technique entre parenthèses | l'inverse |
| `Explanation` | encadré visible | ligne discrète |

Des composants plutôt que des `if (isTechnical)` disséminés dans les pages,
parce qu'une condition finit toujours par *supprimer* quelque chose. Le détail
technique est masqué par l'attribut `hidden`, jamais retiré du DOM : il reste
trouvable par une recherche dans la page et par un lecteur d'écran, et le
dirigeant qui déplie voit exactement ce que voit son prestataire.

`Term` affiche **toujours les deux** formulations. Masquer « SPF » au
dirigeant l'empêcherait de reconnaître le mot dans le courriel de son
prestataire — c'est-à-dire exactement au moment où il en a besoin.

## Conséquences

Le basculement vit dans la barre du haut, présente sur tous les écrans : la
consigne demande qu'il se change à tout moment, et un réglage qu'il faut aller
chercher dans un menu ne se change jamais. Le changement est optimiste et
persisté en arrière-plan ; un échec réseau ramène l'affichage à l'état
enregistré plutôt que de laisser l'écran mentir.

Le profil est appliqué aujourd'hui au plan d'action (référence de la mesure)
et à la surveillance (ce que le contrôle a constaté). Les autres écrans
l'ignorent encore : les primitives existent, leur application est un travail
d'écran par écran qui se poursuivra. C'est dit dans le journal plutôt que
laissé à découvrir.
