# ADR-040 — Écrire des cours, les dire à voix haute, et les remplir avec les données du client

- **Statut** : accepté
- **Date** : 2026-09-21
- **Contexte** : Module Formation, lot 2 (F2). Prolonge
  [ADR-039](039-former-les-salaries-sans-leur-creer-de-compte.md), reprend la
  séparation catalogue/attribution d'[ADR-029](029-referentiels-multiples-et-attribution.md)
  et la règle d'[ADR-014](014-secret-handling-breach-data.md) sur les espaces
  clients.

## Décision 1 — Un seul studio, deux propriétaires

`Course.owner_tenant` nul désigne un cours de **bibliothèque**, écrit par
l'exploitant ; renseigné, un cours écrit par un client. C'est le seul champ
qui distingue les deux, et il n'existe qu'un jeu de fonctions pour les deux.

Un client dont l'offre comprend le studio peut **dériver** un cours de la
bibliothèque. La copie est complète et indépendante : republier l'original ne
change rien à la copie. Le lien `derived_from` est conservé pour retrouver
d'où vient un cours, pas pour le synchroniser.

**Un administrateur plateforme ne peut pas ouvrir le cours d'un client**, bien
qu'il en ait techniquement le pouvoir. La copie appartient au client, ses
phrases comprises. C'est ADR-014 appliqué à un nouvel objet.

## Décision 2 — Une version publiée ne se modifie pas

Corriger une phrase pendant qu'un salarié suit le cours ne décale pas
seulement ses écrans : une ligne de progression désigne un écran, et l'écran
aurait changé de sens. La progression enregistrée deviendrait fausse sans que
rien ne le signale.

On crée donc une nouvelle version, copie de la précédente. Les inscriptions en
cours restent sur la leur ; les suivantes démarrent sur la nouvelle.

**Le point délicat est la recopie** : chaque question de la copie est
repointée vers l'écran correspondant de la copie. Sans cela, la révision après
échec renverrait dans une autre version du cours — et rien ne le dirait.

Au plus un brouillon par cours : deux brouillons simultanés posent la question
insoluble de savoir lequel publier.

## Décision 3 — La voix vient du navigateur, et rien n'est stocké

### Ce qui a été mesuré avant de choisir

Le cours de démonstration fait 3 507 caractères d'écrans. Trois fournisseurs
ont été chiffrés :

| Fournisseur | Prix par million | Un cours, généré une fois |
|---|---|---|
| Amazon Polly Neural (Paris) | 16 $ | 0,06 $ |
| Amazon Polly Generative | 30 $ | 0,11 $ |
| ElevenLabs Multilingual v2 | 100 $ | 0,35 $ |

La règle initiale — générer une fois à la publication et stocker le fichier —
existait pour maîtriser ces coûts, et elle se vérifiait : à chaque écoute,
100 salariés écoutant deux fois auraient coûté **11 $ par cours chez Polly,
70 $ chez ElevenLabs**.

### La décision, et pourquoi elle annule la précédente

**Aucun fournisseur payant**, faute de budget. La lecture se fait par la
synthèse du navigateur (`window.speechSynthesis`), sur l'appareil de
l'apprenant.

La règle « générer une fois et stocker » **tombe** : elle protégeait d'un coût
qui n'existe plus. Rien n'est généré côté serveur, rien n'est stocké, aucun
fichier audio n'entre dans les sauvegardes.

### Ce que ce choix fait gagner, au-delà du prix

Il **dissout un conflit** que la génération côté serveur créait : l'audio
était produit une fois par version, alors qu'un écran contextualisé affiche
des chiffres propres à chaque client et changeants. Il aurait fallu soit
générer par client et par jour — en envoyant les données du client à un
tiers —, soit priver de voix les écrans contextualisés.

Comme la voix parle localement, **un écran contextualisé se lit intégralement,
chiffres compris, sans qu'aucune donnée ne quitte l'appareil**.

### Ce que ce choix coûte, et qui est assumé

La qualité et la disponibilité des voix varient d'un appareil à l'autre, et
nous ne les maîtrisons pas. Trois garde-fous :

1. si le navigateur ne sait pas parler, **rien n'est affiché** et le cours
   reste entièrement utilisable ;
2. si aucune voix française n'est installée, une phrase discrète le dit —
   jamais une erreur technique ;
3. l'audio est une **aide** : le texte reste à l'écran, la voix se coupe, et
   la coupure est retenue d'un écran à l'autre.

Deux défauts connus de cette interface sont traités explicitement : la voix
est arrêtée au changement d'écran et à la sortie de la page (sans quoi elle
poursuit le texte précédent), et le texte est énoncé **bloc par bloc** parce
que plusieurs moteurs coupent les textes longs sans rien signaler.

### Pour plus tard

La lecture est isolée derrière un lecteur (lire / pause / arrêter). Un moteur
libre auto-hébergé — Piper, par exemple — pourrait s'y brancher sans toucher
aux écrans. **Rien n'est installé aujourd'hui.** Le jour venu, les licences
des voix Piper seront à vérifier **voix par voix** : elles diffèrent, et
certaines interdisent l'usage commercial.

## Décision 4 — Ce qui peut être injecté dans un cours, et ce qui ne peut pas

C'est la décision la plus sensible du lot : un cours est lu par **tous** les
salariés d'une entreprise.

### Ce qui peut l'être

Des **agrégats, et uniquement des nombres** : compromissions ouvertes,
compromissions critiques, score d'exposition, score de maturité, actifs
surveillés.

### Ce qui ne peut pas l'être, et comment c'est garanti

**Aucune donnée nominative, aucun mot de passe même partiel.** La garantie
n'est pas une consigne de rédaction : **une variable rend un entier**. Il
n'existe aucun chemin par lequel un nom, une adresse ou un domaine pourrait
atteindre un cours — pas même par l'erreur d'un auteur. Un test parcourt le
registre et vérifie le type rendu ; ajouter une variable de texte le ferait
rougir.

### La règle que la consigne ne couvrait pas : les petits nombres

« Jamais de donnée nominative » ne suffit pas. Dans une entreprise de six
personnes, « 1 compte compromis » désigne quelqu'un aussi sûrement qu'un nom.

**En dessous de trois**, un décompte est traité comme indisponible et le bloc
bascule sur sa formulation de repli. Trois est un choix, pas un seuil
réglementaire : c'est le premier nombre au-dessus duquel un salarié ne peut
plus deviner « c'est moi ». Le seuil ne s'applique pas aux scores, qui ne
désignent personne.

### Le repli, et pourquoi il porte sur le bloc entier

Le repli s'applique au bloc, jamais à la variable seule — sinon on produirait
« votre entreprise a — comptes compromis ». Un bloc se lit d'un tenant ou pas
du tout. Il est **obligatoire** dès qu'un bloc contient une variable, et le
serveur refuse l'écriture sans lui.

Les valeurs sont calculées **à l'affichage** et ne sont stockées nulle part.

## Décision 5 — Une seule marque de mise en forme

Le gras, écrit `**ainsi**`, rendu par découpage en segments et jamais par du
HTML. Cela revient sur la règle de F1 (« aucune marque en ligne »), qui avait
été posée pour éviter un analyseur de texte libre. Une marque unique, sans
grammaire, ne rouvre pas cette porte. Le détail est dans
[`docs/format_blocs_formation.md`](../format_blocs_formation.md).

## Conséquences

- Une clé de registre, `training_studio`, ajoutée à « Pilotage » et
  « Souverain ». Sans quota : écrire un cours ne consomme aucune ressource
  rare, et la voix ne coûte rien.
- **La première dépendance réelle entre deux clés** (`DEPEND_DE`) :
  `training_studio` exige `training`. Écrire des cours sans pouvoir les faire
  suivre n'a pas de sens. La table était vide depuis ADR-038, par constat
  vérifié ; elle ne l'est plus, et le mécanisme prévu pour ce jour s'applique.
- Le refus pour cause d'offre est un **402**, jamais un 403 : le rôle est
  jugé par la permission, l'offre par la vue. La lecture de la bibliothèque
  reste servie hors offre (ADR-019).
- Le studio vit sur `/studio` et non sous `/formation` : cette adresse porte
  déjà la route publique `/formation/:token`, où « studio » passerait pour un
  jeton d'apprenant.
- **Les images ne sont pas livrées dans ce lot.** Le produit n'a aujourd'hui
  aucun stockage de fichiers — ni `MEDIA_ROOT`, ni volume, ni sauvegarde des
  fichiers. Les livrer supposait de trancher l'emplacement, le contrôle
  d'accès (un cours de client peut être interne), le réencodage à la réception
  pour retirer les métadonnées, et l'entrée de ces fichiers dans la
  sauvegarde. Le format de blocs accepte déjà les images ; l'infrastructure
  qui les recevrait reste à décider.
