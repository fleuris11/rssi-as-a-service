# Format des blocs de contenu — module Formation

> Source unique : `backend/apps/training/blocks.py`.
> Ce document explique **pourquoi** et sert de contrat au studio de F2.
> Le code fait foi pour les valeurs.

Le contenu d'un écran de cours n'est pas du texte libre : c'est une **liste de
blocs typés**, stockée en JSON dans `Screen.content`, et **validée au moment
de l'écriture**.

## Pourquoi pas du Markdown

Le Markdown existait déjà dans le produit, pour les documents composés. Il n'a
pas été repris ici, et la raison n'est pas esthétique :

- le contenu d'un document est **lu** ; celui d'un écran de formation sera
  **découpé**. F2 doit pouvoir le dire à voix haute phrase par phrase et y
  injecter des variables (le nom de l'entreprise, son secteur). Les deux
  supposent de savoir où commence un paragraphe et où finit une légende ;
- sur du texte libre, cela demande un analyseur — qui se trompera sur les cas
  tordus. Sur des blocs typés, c'est une boucle ;
- un bloc `image` peut **exiger** son texte alternatif. Une image Markdown ne
  le peut pas : `![](photo.png)` est syntaxiquement valide, et c'est exactement
  ce qui exclut un salarié qui utilise un lecteur d'écran.

## La règle qui commande le reste

**Un contenu mal formé est refusé à l'écriture, jamais découvert à la
lecture.** La validation vit dans `Screen.save()`, donc sur tous les chemins
d'écriture : la commande de chargement de F1, et le studio de F2. Conséquence
voulue — la lecture ne valide rien et ne peut donc pas échouer. Le lecteur de
cours n'a pas de chemin d'erreur pour cause de contenu mal formé, et un salarié
dans le train ne verra jamais « contenu invalide ».

## Les six blocs

Chaque bloc est un objet portant un champ `type`. Tout champ non listé est
ignoré à la lecture, mais **le type doit être connu** : un type inconnu est
refusé, sans quoi un écran pourrait être enregistré puis s'afficher vide.

### `paragraphe`

```json
{ "type": "paragraphe", "texte": "Un message qui vous presse est un signal." }
```

`texte` : obligatoire, non vide, 4 000 caractères au plus.

### `titre`

```json
{ "type": "titre", "niveau": 3, "texte": "Les trois signes qui doivent alerter" }
```

`niveau` : **3 ou 4 uniquement**. Le titre de l'écran occupe déjà le niveau 2
dans la page. Autoriser un `h1` ou un `h2` ici casserait la hiérarchie des
en-têtes — or c'est par les en-têtes qu'on navigue avec un lecteur d'écran.
C'est une contrainte d'accessibilité, pas de mise en page.

### `liste`

```json
{ "type": "liste", "ordonnee": false, "items": ["Vérifiez l'adresse", "Appelez"] }
```

`items` : liste non vide, 20 entrées au plus, chaque entrée non vide.
`ordonnee` : facultatif, booléen, faux par défaut. Vrai rend une liste
numérotée — à réserver aux marches à suivre, où l'ordre a un sens.

### `encadre`

```json
{ "type": "encadre", "ton": "attention", "texte": "Ne répondez jamais par retour de courriel." }
```

`ton` : `info`, `attention` ou `exemple`. Trois valeurs et pas de couleur
libre : le ton dit une **nature de propos**, pas une décoration. Une palette
ouverte aurait fait dériver le sens vers l'apparence, et l'apparence vers
l'arbitraire.

### `image`

```json
{ "type": "image", "source": "/formation/hameconnage-entete.svg", "alternative": "Un courriel dont l'adresse d'expéditeur imite celle de la banque." }
```

`source` : doit commencer par `/formation/` et ne pas contenir `..`. Les
images de F1 sont **livrées avec l'application**, jamais téléversées : pas de
studio en F1, donc pas de dépôt de fichier, donc aucune question de stockage ni
d'analyse antivirale à trancher dans ce lot. Le préfixe est vérifié pour que ce
choix ne puisse pas être contourné en glissant une URL externe dans un cours —
ce qui ferait fuiter l'adresse IP de chaque salarié vers un tiers à chaque
ouverture d'écran.

`alternative` : **obligatoire**, non vide. Voir plus haut.

### `citation`

```json
{ "type": "citation", "texte": "…", "source": "ANSSI, guide d'hygiène informatique" }
```

`source` : facultative ; si elle est présente, elle doit être non vide.

## Le gras (F2)

Une **seule** marque en ligne, et elle s'écrit `**comme ceci**`.

F1 n'en autorisait aucune, et disait pourquoi : autoriser des marques rouvre
la porte à l'analyseur qu'on cherchait à éviter. Le studio de F2 en demande
une — mettre un mot en valeur est le minimum vital pour un auteur.

Ce qui rend la chose sûre n'est pas la marque mais le **rendu** : le texte est
découpé en segments (`blocks.segments()`), et l'interface met les uns en gras.
Rien de ce qu'écrit un auteur n'atteint le navigateur sous forme de balise —
l'injection est impossible par construction, pas par filtrage.

Une marque non fermée est **refusée à l'écriture**. La lecture, elle, reste
tolérante : elle affiche le texte brut plutôt que d'inventer une
interprétation.

## Les variables contextuelles (F2)

Un texte peut contenir `{score_maturite}`. Les clés disponibles sont déclarées
dans `backend/apps/training/variables.py` et **proposées par le studio** : on
n'écrit pas une variable qui n'existe pas, et une clé inconnue est refusée à
l'écriture.

### La formulation de repli est obligatoire

Dès qu'un bloc contient une variable, il **doit** porter un champ `repli` :

```json
{
  "type": "paragraphe",
  "texte": "Votre entreprise a {fuites_ouvertes} comptes compromis.",
  "repli": "Des comptes de votre entreprise pourraient déjà circuler dans des fuites."
}
```

Le repli est affiché — pour le **bloc entier**, jamais variable par variable —
dans quatre cas :

1. la donnée n'existe pas (client neuf, diagnostic jamais fait) ;
2. elle vaut zéro : « vous avez eu 0 incident » annoncé sur le ton de l'alerte
   est au mieux ridicule ;
3. le décompte est **inférieur à 3** : dans une entreprise de six salariés,
   « 1 compte compromis » désigne quelqu'un sans le nommer ;
4. la variable relève d'une fonctionnalité absente de l'offre du client.

Le repli ne peut pas lui-même contenir de variable — c'est précisément le
texte affiché quand les variables manquent.

Les valeurs sont calculées **à l'affichage**, jamais figées à l'inscription,
et ne sont recopiées nulle part : ni dans la progression, ni dans la
tentative, ni dans l'attestation.

## Ce que le format ne fait pas

- **Pas de HTML, et aucune autre marque que le gras.** Un bloc porte du texte
  brut. Ajouter l'italique ou les liens rouvrirait la porte à l'analyseur
  qu'on cherche à éviter.
- **Aucune variable de texte.** Une variable rend un nombre. C'est ce qui rend
  impossible qu'un nom, une adresse ou un mot de passe se retrouve dans un
  cours — y compris par erreur d'un auteur (ADR-040).
- **Pas de vidéo** (décision de cadrage F1) : lourde à produire, à héberger, et
  inutilisable sans sous-titres — qui sont eux-mêmes un travail de production.
- **Pas d'imbrication.** Une liste ne contient pas de blocs, un encadré ne
  contient pas d'image. La liste de blocs est plate, et le rendu s'en trouve
  prévisible sur un écran de téléphone.

## Pour le studio de F2

Le studio n'invente rien : il produit ces six blocs, et se repose sur
`blocks.valider()` pour refuser. Toute extension du format passe par ce module
et par une mise à jour de ce document — un studio qui écrirait un septième type
« que le lecteur sait afficher » créerait un format parallèle non validé.
