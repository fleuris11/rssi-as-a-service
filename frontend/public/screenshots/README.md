# Captures d'écran du site vitrine

Ce dossier accueille les **captures réelles du produit** affichées sur la page
d'accueil. Tant qu'un fichier est absent, la vitrine affiche à la place une
reconstitution en CSS de l'interface (`src/marketing/components/ExposureMockup.jsx`)
— jamais une photo d'illustration générique.

**Déposer le fichier suffit** : aucune modification de code n'est nécessaire.
Le cadre demande l'image et retombe sur la reconstitution si elle est absente
(`src/marketing/components/CaptureProduit.jsx`).

> Ce n'était pas vrai jusqu'au 27/08/2026 : ce document décrivait la marche à
> suivre, mais aucun code ne lisait ces fichiers. Déposer `exposition.png`
> n'avait aucun effet. Corrigé — le document décrit maintenant un
> comportement, pas une intention.

## Fichiers attendus

| Fichier | Écran à capturer | Où il apparaît |
|---|---|---|
| `exposition.png` | Page Exposition, premier actif déplié, bandeau Analyse visible | Accroche de la page d'accueil |
| `radar.png` | Carte « Signaux avant-coureurs » avec au moins deux signaux | Bloc « Signaux avant-coureurs » |
| `revelation.png` | Modale de révélation, secret affiché avec son compte à rebours | Bloc « Réutilisation possible » |

## Comment les produire

1. Lancer la stack et peupler le tenant de démonstration :
   ```bash
   docker compose up -d
   docker compose exec web python manage.py seed_demo_tenant --reset
   ```
2. Ouvrir le produit sur `http://localhost:5173`, se connecter avec le compte
   de démonstration (voir `docs/demo_runbook.md`).
3. Capturer en **largeur de fenêtre 1440 px**, zoom 100 %, thème clair, avec
   un facteur d'échelle de 2 (`deviceScaleFactor: 2`) — la capture brute fait
   alors 2880 px de large.
4. Redimensionner à **1456 px de large**, puis compresser (viser moins de
   250 Ko : l'accroche est la première impression, et une image lourde la
   retarde).

## Dimensions exactes

Mesurées sur la page, à chaque point de rupture — pas déduites d'une maquette :

| Fenêtre | Largeur d'affichage du cadre |
|---|---|
| 1440 px et au-delà | 511 px (accroche) / 546 px (aperçus) |
| 1024 px | 449 px / 462 px |
| **768 px** | **728 px** — le maximum, la mise en page passant en colonne unique |
| 390 px | 350 px / 348 px |

**Produire les trois fichiers en 1456 px de large.** C'est le double du
maximum d'affichage (728 px), donc net sur un écran à densité double, et
inutile d'aller au-delà : l'image ne sera jamais affichée plus large.

La **hauteur est libre** — le cadre s'y adapte. Viser un rapport proche de
**1,3:1** (soit environ 1456 × 1120) pour l'accroche : plus haut, l'image
domine le titre, ce qui est précisément ce qu'on ne veut pas dans un bloc dont
l'accroche doit se lire en premier.

## Deux règles

- **Uniquement des données du tenant de démonstration.** Aucune capture d'un
  espace client réel, même anonymisée : le risque d'oublier un détail
  identifiant est trop élevé pour le gain.
- **Recapturer après toute refonte visuelle.** Une capture qui ne correspond
  plus à l'interface se remarque immédiatement en démonstration, et coûte
  davantage en crédibilité qu'elle n'apporte.

## Brancher une capture

Dans `src/marketing/pages/LandingPage.jsx`, passer le chemin au composant :

```jsx
<BrowserFrame src="/screenshots/exposition.png" alt="La page Exposition…" />
```

Le composant bascule automatiquement de la reconstitution CSS vers l'image.
Renseigner un `alt` **descriptif** : il est lu par les lecteurs d'écran et
affiché si l'image ne charge pas.
