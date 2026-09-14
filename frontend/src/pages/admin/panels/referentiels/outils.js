// Outils partagés par les écrans d'édition du catalogue (lot B). Dans un
// fichier séparé des composants : un module qui exporte à la fois des
// composants et des fonctions casse le rechargement à chaud de Vite.

/** Un identifiant lisible à partir d'un nom : « Règles internes » →
 *  « regles-internes ». Même forme que `slugify` côté serveur, qui reste
 *  l'autorité : il refuse ce qu'il n'aurait pas produit. */
export function versIdentifiant(texte) {
  return (texte || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
}

/** Proposer un fichier reçu de l'API. Le contenu passe par un blob chargé
 *  AVEC le jeton : un lien direct vers une route authentifiée échouerait. */
export function telechargerBlob(blob, nom) {
  const url = URL.createObjectURL(blob)
  const lien = document.createElement('a')
  lien.href = url
  lien.download = nom
  lien.click()
  URL.revokeObjectURL(url)
}

/** Le texte d'un fichier choisi par l'utilisateur. */
export function lireFichier(fichier) {
  return new Promise((resoudre, rejeter) => {
    const lecteur = new FileReader()
    lecteur.onload = () => resoudre(String(lecteur.result || ''))
    lecteur.onerror = () => rejeter(lecteur.error)
    lecteur.readAsText(fichier, 'utf-8')
  })
}

export const NIVEAUX = [
  { value: 'low', label: 'Faible' },
  { value: 'medium', label: 'Moyen' },
  { value: 'high', label: 'Élevé' },
]

export const CHAMP =
  'mt-1 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm'
