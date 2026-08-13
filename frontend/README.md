# Frontend

React 18 + Vite + Tailwind CSS. Voir le [README racine](../README.md) pour la
place de cette brique dans le projet et le démarrage complet.

```bash
npm install
npm run dev      # http://localhost:5173
npm run lint
npm run build
```

## Tests

Deux suites, deux rôles distincts :

```bash
npm test          # Vitest — composants, en mémoire (jsdom), quelques secondes
npm run test:watch
npm run test:e2e  # Playwright — parcours réels, nécessite la stack lancée
```

### Tests de composants (Vitest + Testing Library)

Fichiers `src/**/*.test.jsx`, à côté du composant testé. Les deux jobs CI
correspondants (`frontend-unit` et `e2e`) sont bloquants.

La suite ne vise **pas** la couverture exhaustive mais les endroits où une
régression serait à la fois silencieuse et coûteuse :

| Cible | Ce qui est verrouillé |
|---|---|
| `RevealSecretModal` | Ré-authentification, état de chargement, garde anti-double-soumission, **un seul appel réseau sur identifiants refusés** (régression Phase 7), masquage automatique du secret à 30 s |
| `PreIncidentRadar` | Actions de traitement, mode historique, état vide (message commercial autant qu'état d'interface) |
| `ExposureScoreDial` | Affiche le score du serveur sans le recalculer, bornes du cadran |
| `ExposurePage` | Composantes du score, fuite au secret purgé, vocabulaire de corrélation non reformulé, politique de conservation |

Les règles métier (calcul du score, vulgarisation, vocabulaire de corrélation)
vivent côté backend et y sont testées. Le risque couvert ici est que le
frontend les **déforme ou les perde en route**, pas qu'elles soient fausses.

### Écrire un test

`src/test/setup.js` fournit les matchers `jest-dom`, le nettoyage entre tests
et des stubs jsdom (presse-papier, `scrollIntoView`).

Deux pièges rencontrés, à connaître :

- **Minuteurs.** Pour tester le masquage automatique, utiliser
  `vi.useFakeTimers({ shouldAdvanceTime: true })` : sans `shouldAdvanceTime`,
  `waitFor` (qui sonde sur l'horloge réelle) et les promesses de l'appel API
  restent bloqués sous horloge figée.
- **« Fermer » est ambigu** dans une modale : l'arrière-plan, la croix et le
  bouton de pied portent tous ce libellé. Viser explicitement celui qu'on veut.
