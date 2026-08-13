# Captures d'écran du site vitrine

Ce dossier accueille les **captures réelles du produit** affichées sur la page
d'accueil. Tant qu'un fichier est absent, la vitrine affiche à la place une
reconstitution en CSS de l'interface (`src/marketing/components/ExposureMockup.jsx`)
— jamais une photo d'illustration générique.

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
3. Capturer en **largeur 1440 px**, zoom 100 %, thème clair.
4. Enregistrer en PNG, largeur 1440 px maximum, puis compresser (l'accroche
   est la première impression : viser moins de 250 Ko par image).

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
