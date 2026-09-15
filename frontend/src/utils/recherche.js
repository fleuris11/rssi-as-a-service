/**
 * La recherche côté écran (lot C, point 22).
 *
 * Insensible à la casse ET aux accents : un dirigeant qui tape « securite »
 * cherche « sécurité ». Sans cette normalisation, la moitié des recherches
 * en français échouent sur une lettre.
 */

export function normaliser(texte) {
  return String(texte ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim()
}

/**
 * Les lignes dont au moins un champ contient la recherche.
 *
 * @param {Array} lignes
 * @param {string} recherche
 * @param {(ligne) => Array} extraire  les textes d'une ligne dans lesquels chercher
 */
export function filtrerParTexte(lignes, recherche, extraire) {
  const aiguille = normaliser(recherche)
  if (!aiguille) return lignes
  return lignes.filter((ligne) => extraire(ligne).some((valeur) => normaliser(valeur).includes(aiguille)))
}
