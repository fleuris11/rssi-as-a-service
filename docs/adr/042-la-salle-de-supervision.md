# ADR-042 — La salle de supervision : changement de direction visuelle

- **Statut** : accepté
- **Date** : 2026-09-22
- **Remplace** : la direction « le trait plutôt que l'ombre » (septembre 2026,
  non documentée par un ADR, décrite dans `docs/systeme_visuel.md`)
- **Détail** : `docs/design.md`

## Contexte

La direction visuelle précédente avait été jugée par le commanditaire
« propre, mais fade, monotone, aux couleurs ternes, sans aucun effet waouh »,
et la vitrine « trop dense : le visiteur se perd ». Elle avait été construite
par retrait — supprimer les ombres, les cartes, les icônes — sans jamais
choisir un monde à la place. Un système qui n'est qu'une liste d'interdits ne
produit pas de caractère ; il produit du vide bien rangé. C'est ce qui s'est
passé.

Par ailleurs le produit porte une contrainte que la direction précédente
traitait comme un réglage secondaire : il doit dire la même chose à un gérant
de PME non informaticien et à son prestataire technique. Les profils
d'affichage Dirigeant et Technique existaient, mais ils se ressemblaient trop
pour que la différence se voie.

## Options

1. **Corriger la direction existante** — plus de contraste, une couleur
   d'accent plus vive, des titres plus gros. Rejeté : c'est le polissage d'un
   choix qui n'a jamais été fait. Le reproche portait sur l'absence de parti
   pris, pas sur des réglages.
2. **Adopter l'esthétique dominante des outils de sécurité** — fond sombre,
   accent néon, carte de menaces animée. Rejeté : c'est l'ornière de la
   catégorie, immédiatement reconnaissable comme du web généré, et le fond
   sombre est contraire à la scène d'usage réelle (un gérant lit sur son
   téléphone, en plein jour, depuis un email).
3. **Adopter le monde d'un tableau de supervision de réseau public français**
   — le couple éCO2mix / Ecowatt : une console d'exploitant et un signal
   public qui lisent la même donnée. Retenu.
4. **Le bulletin de vigilance Météo-France** — quatre couleurs, un bulletin
   horodaté. Rejeté : le produit envoie déjà une « météo cyber », le monde
   serait la lecture littérale de son propre nom ; et la vigilance ne sait
   parler qu'à un seul lecteur, elle n'a pas de seconde surface pour l'expert.
5. **Le procès-verbal de contrôle technique automobile** — défaillances
   mineures / majeures / critiques, date de la prochaine visite. Rejeté : un
   contrôle technique est un événement ponctuel, le produit surveille en
   continu. Le monde aurait menti sur le mécanisme.

## Décision

Le produit prend la forme d'un **pupitre de conduite** : un bâti graphite
(rail, bandeau d'état, pied de page) autour d'une **face d'instrument claire
et réglée** où se lit le contenu.

Quatre règles structurantes en découlent.

1. **Le bandeau d'état est le signal public.** Présent sur les trois surfaces,
   il porte un cran, une phrase et une seule action. Il se gorge de sa couleur
   quand le cran atteint `critique` — c'est le seul endroit du produit où une
   couleur occupe une grande surface.
2. **La couleur ne dit que le risque.** Quatre crans, empruntés au vocabulaire
   de la vigilance publique française, chacun doublé d'un mot et d'un glyphe.
   Une seule couleur d'action, qui n'est jamais un état. Le champ de lecture
   reste achromatique.
3. **Dirigeant et Technique ne sont plus un réglage, ce sont deux surfaces.**
   Dirigeant reçoit le signal public : densité confortable, trois indicateurs
   au maximum, des phrases, la décision à prendre. Technique reçoit la console :
   densité compacte, colonnes triables, filtres, export, vocabulaire exact.
   Même donnée, même seconde, deux rendus — jamais deux chiffres différents.
4. **La profondeur vient d'un filet, pas d'une ombre**, et rien ne glisse : un
   changement d'état saute d'un cran entier, dépasse, se pose.

La typographie change : **Archivo Variable** (avec son axe de largeur) et
**Chivo Mono Variable** remplacent Fraunces et Inter. Les deux sont sous
licence SIL OFL et auto-hébergées ; aucune requête de police ne sort du
navigateur.

## Conséquences

**Ce que ça coûte.**

- Tout le front est touché : vitrine, authentification, espace client, console.
  La refonte se fait surface par surface, un commit par surface, avec captures
  avant/après et tests verts à chaque étape.
- Les sélecteurs de test qui s'appuyaient sur des classes de l'ancienne
  direction cassent. Ils sont réparés sur des rôles et des libellés, pas
  rafistolés sur de nouvelles classes.
- `docs/systeme_visuel.md` devient caduc et renvoie vers `docs/design.md`.
- La classe `.t-eyebrow` disparaît : les sur-titres au-dessus des titres de
  section sont supprimés du produit.

**Ce que ça ne change pas.**

- **Aucune fonctionnalité ni donnée n'est retirée.** Le backend ne bouge pas.
  Les gardes 402, le cloisonnement multi-client, la révélation de secret, les
  droits par rôle et la journalisation d'audit restent strictement intacts.
- Aucun service payant ni appel externe au moment de l'exécution : polices et
  bibliothèques auto-hébergées, aucune dépendance d'animation ajoutée.
- L'exigence WCAG AA reste vérifiée par axe-core dans la CI, au même seuil.

**Filet de secours.** L'état déployé avant la refonte porte le tag
`avant-refonte` (commit `95cb679`). Retour arrière :
`git revert` de la plage, ou redéploiement du tag.

## Décisions de méthode consignées ici parce qu'elles engagent

- La direction n'a pas été choisie par goût : elle a été tirée par
  `impeccable concept-seed` (graine `22c7b0c6`, index assigné 4) parmi sept
  directions ancrées classées par résonance, précisément pour ne pas retomber
  sur la première — celle que tout modèle proposerait. Les six mondes adverses
  tirés ont été pesés et leur verdict est écrit dans `docs/design.md`.
- `PRODUCT.md` a été écrit **sans entretien**, sur consigne explicite du
  commanditaire de ne pas s'arrêter pour validation. Toutes les déductions y
  sont marquées `[déduit]`. C'est une entorse assumée au protocole du skill,
  signalée ici pour qu'on sache d'où vient le fichier.
