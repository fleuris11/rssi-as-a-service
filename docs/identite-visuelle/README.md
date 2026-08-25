# Identité visuelle

## Fichiers servis par le site

Générés à partir du logo source, aux dimensions réellement affichées.

| Fichier | Dimensions | Usage |
|---|---|---|
| `logo-embleme.webp` / `@2x` | 64 / 128 px | En-tête de la vitrine et de l'espace client |
| `logo-complet.webp` / `@2x` | 320 / 640 px | En-tête de l'administration (fond sombre) |
| `og-image.jpg` | 1200×630 | Aperçu lors du partage d'un lien |
| `favicon.ico` | 16/32/48 px | Onglet du navigateur |
| `apple-touch-icon.png` | 180 px | Écran d'accueil iOS |

Ils vivent dans `frontend/public/` et sont versionnés.

## Le fichier source n'est pas ici

Le logo d'origine (PNG, ~1,3 Mo) **ne doit pas être placé dans
`frontend/public/`** : tout ce que contient ce dossier est servi publiquement
et téléchargeable. Rangez-le hors du dépôt, ou dans un dossier non servi.

## Regénérer les dérivés

Si le logo change, refaire les fichiers ci-dessus **aux mêmes dimensions**.
Le point à ne pas manquer : les tailles sont calées sur l'affichage réel
(l'emblème se voit à 32 px), pas sur la source. Un fichier de 256 px pour un
affichage de 32 px n'apporte rien qu'un écran sache montrer, et alourdit la
première page que voit un visiteur — le cadrage impose un budget de
performance (Green IT, CLAUDE.md).

## Pourquoi le logo n'est pas détouré

Il est dessiné sur un fond sombre, avec un dégradé et un halo. Un détourage
laisse un liseré visible, précisément sur le premier élément que voit un
visiteur. Il est donc posé dans une tuile foncée sur les fonds clairs, et
affiché tel quel sur les fonds déjà sombres (en-tête d'administration).
