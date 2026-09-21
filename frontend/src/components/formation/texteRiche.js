/**
 * Le gras, sans jamais passer par du HTML.
 *
 * Le serveur stocke le texte tel que l'auteur l'a écrit, marques comprises
 * (`**comme ceci**`), et le valide à l'écriture. Ici on le découpe en
 * segments ; React met les uns en `<strong>` et les autres non. Rien de ce
 * qu'écrit un auteur n'atteint le navigateur sous forme de balise — c'est ce
 * qui rend l'injection impossible par construction plutôt que par filtrage.
 *
 * Miroir de `blocks.segments()` côté serveur. Les deux sont volontairement
 * simples : une marque, pas de grammaire.
 */

export const MARQUE_GRAS = '**'

export function segmentsGras(texte = '') {
  const morceaux = String(texte).split(MARQUE_GRAS)
  // Nombre impair de marques : l'auteur en a laissé une ouverte. Le serveur
  // refuse ce cas à l'écriture ; si jamais il arrive ici, on affiche le texte
  // brut plutôt que d'inventer une interprétation.
  if (morceaux.length % 2 === 0) return [{ texte: String(texte), gras: false }]

  return morceaux
    .map((morceau, index) => ({ texte: morceau, gras: index % 2 === 1 }))
    .filter((segment) => segment.texte !== '')
}

/** Le texte débarrassé de ses marques — pour la lecture à voix haute. */
export function sansMarques(texte = '') {
  return segmentsGras(texte)
    .map((segment) => segment.texte)
    .join('')
}
