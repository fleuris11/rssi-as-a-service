# 018 — Site vitrine public dans l'application existante

- **Statut** : Adopté ; implémenté en Phase 9
- **Date** : 2026-08-13

## Contexte

Jusqu'ici, `/` ouvrait directement l'écran de connexion : un visiteur qui
découvrait le produit tombait sur un formulaire, sans savoir ce qu'il achetait.
Il fallait une vitrine publique, destinée à de vrais prospects, menant soit à
une demande de démonstration, soit à la connexion pour les clients existants.

Trois questions se posaient : où vit ce site, comment garantir que le discours
reste vrai, et comment un formulaire public ne devienne pas une porte d'entrée
à spam sur une plateforme qui vend de la sécurité.

## Décision 1 — La vitrine vit dans l'application React existante

Options écartées :

- **Un site séparé** (générateur statique, autre dépôt, autre déploiement).
  Plus rapide à charger et découplé, mais deux dépôts à maintenir, deux
  chaînes de build, deux déploiements, et surtout une palette et des
  composants qui divergeraient — sur un produit dont l'argument est la
  sobriété et la cohérence, une vitrine qui ne ressemble pas au produit se
  remarque.
- **Un rendu côté serveur** (Django templates). Cohérent avec le backend,
  mais imposerait de réimplémenter en Jinja les composants déjà écrits en
  React, et de maintenir deux systèmes de style.

Retenu : **mêmes dépôt, même build, mêmes composants**, avec une séparation
nette dans l'arborescence (`src/marketing/`) et surtout **au chargement**.

Le point qui rend ce choix tenable est le découpage : `App.jsx` importe la
page d'accueil normalement (c'est la première page, la différer ajouterait un
aller-retour avant le premier pixel) et charge **tout le reste à la demande**,
y compris l'application authentifiée (`AppRoutes.jsx`, extrait pour former ce
point de coupe). Un visiteur ne télécharge donc pas le tableau de bord, le
kanban et les graphiques qu'il ne verra peut-être jamais : le build produit
bien deux paquets distincts (~285 Ko pour l'entrée, ~457 Ko pour
l'application).

Conséquence assumée : les métadonnées de référencement sont posées côté client
(`useSeo.js`), donc invisibles pour un robot qui n'exécute pas JavaScript. Pour
un produit dont l'acquisition passe par la prospection directe et non par le
référencement naturel, c'est acceptable. Si cela changeait, la réponse serait
un pré-rendu des routes publiques, pas un second site.

## Décision 2 — Le contenu est centralisé et vérifié contre le code

Tout le texte de la vitrine vit dans `src/marketing/content.js`, pas dispersé
dans les composants. Deux raisons : la relecture éditoriale se fait d'un seul
coup d'œil, et l'ajout d'une langue consistera à dupliquer cet objet. **L'i18n
n'est pas implémentée** (aucune dépendance ajoutée) : seule la structure y est
prête.

Plus important : **chaque affirmation du fichier doit correspondre à une
fonctionnalité qui existe**. Cette règle n'est pas déclarative, elle est
outillée — des tests de composant échouent si le discours dérive :

- aucune promesse de blocage (« nous bloquons », « protection totale ») : le
  produit détecte et alerte, il n'intervient pas sur les systèmes du client ;
- aucune garantie de conformité ;
- « réutilisation possible », jamais « confirmée » (aucun identifiant n'est
  testé nulle part) ;
- « neuf sources », le nombre réellement interrogé ;
- aucun ciblage géographique, aucun superlatif creux.

La rédaction a d'ailleurs corrigé quatre écarts entre le discours envisagé et
le code réel — voir le journal de cette phase.

## Décision 3 — Anti-spam sans service tiers

Le formulaire public est, avec l'authentification et le webhook, l'un des trois
seuls points d'entrée non authentifiés de la plateforme. Trois protections,
**aucune ne reposant sur un tiers** :

1. **Honeypot** : un champ `website` masqué visuellement, retiré de l'ordre de
   tabulation et de l'arbre d'accessibilité — aucun humain, y compris au
   lecteur d'écran, ne le rencontre. Rempli, la demande est rejetée avec un
   message générique qui ne révèle pas le piège.
2. **Limitation de débit** par IP (3 par heure) : aucun usage légitime ne
   consiste à remplir ce formulaire plus souvent.
3. **Validation stricte** : adresses jetables refusées, mais adresses grand
   public **acceptées** — un artisan à son compte n'a souvent que celles-là, et
   les écarter coûterait plus cher que le spam évité.

**Pas de CAPTCHA** : il chargerait un script tiers sur une page qui promet de
n'en avoir aucun, et pénaliserait surtout les visiteurs légitimes.

## Décision 4 — Aucune mesure d'audience

Aucun traceur, aucun cookie tiers, aucun outil de mesure — donc aucune bannière
de consentement, faute d'objet. Ce n'est pas seulement une position de
principe : sur un produit qui vend la maîtrise des données et affiche une
politique de confidentialité détaillée, charger un traceur publicitaire sur la
page d'accueil serait une contradiction visible par le premier prospect
technique qui ouvre son inspecteur.

Si un besoin de mesure apparaît, la réponse sera un outil sans cookie et sans
donnée personnelle (type comptage côté serveur), documenté ici.

## Conséquences

- Les URL existantes de l'application sont **inchangées** : seule `/` change
  de destination, et une URL inconnue renvoie désormais vers la vitrine plutôt
  que vers l'écran de connexion.
- Le modèle `DemoRequest` est délibérément **hors du périmètre multi-tenant** :
  un prospect n'a pas encore de tenant. C'est l'une des rares tables métier
  sans `tenant_id`, et sa lecture est réservée au back-office plateforme.
- Les pages légales existent mais portent un avertissement visible : leur
  contenu doit être rédigé ou validé par un professionnel du droit. Publier un
  texte juridique inventé aurait été pire que de ne rien publier.
- Les captures d'écran réelles ne sont pas encore déposées ; en attendant, la
  vitrine affiche une reconstitution en CSS de l'interface plutôt qu'une image
  d'illustration générique (voir `frontend/public/screenshots/README.md`).
