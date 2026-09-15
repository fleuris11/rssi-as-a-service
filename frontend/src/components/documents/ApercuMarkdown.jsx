/**
 * Le rendu d'un document composé, pour l'aperçu (lot C, point 14).
 *
 * Volontairement minimal et SANS HTML : les composeurs n'écrivent que des
 * titres, des listes, des tableaux et du gras. Un rendu par `innerHTML`
 * aurait ouvert la porte à tout ce qu'un champ saisi par le client (raison
 * sociale, nom d'actif) pourrait contenir. Ici, tout texte reste du texte.
 *
 * Les passages « à compléter » sont surlignés et comptés : c'est ce que le
 * client doit savoir AVANT de générer — ce que le document ne peut pas dire
 * à sa place.
 */

export const MARQUE_A_COMPLETER = '*[à compléter]*'

export function compterACompleter(markdown) {
  if (!markdown) return 0
  return markdown.split(MARQUE_A_COMPLETER).length - 1
}

function EnLigne({ texte }) {
  // Découpe : la marque « à compléter » d'abord, puis le gras.
  const morceaux = texte.split(MARQUE_A_COMPLETER)
  return morceaux.map((morceau, i) => (
    <span key={i}>
      {morceau.split(/(\*\*[^*]+\*\*)/g).map((bout, j) =>
        bout.startsWith('**') && bout.endsWith('**') && bout.length > 4 ? (
          <strong key={j}>{bout.slice(2, -2)}</strong>
        ) : (
          <span key={j}>{bout.replace(/^\*([^*]+)\*$/, '$1')}</span>
        )
      )}
      {i < morceaux.length - 1 && (
        <mark className="rounded bg-warning-subtle px-1 text-warning-strong">à compléter</mark>
      )}
    </span>
  ))
}

function cellules(ligne) {
  return ligne
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim())
}

export function blocs(markdown) {
  const lignes = (markdown || '').split('\n')
  const resultat = []
  let i = 0
  while (i < lignes.length) {
    const ligne = lignes[i]
    if (!ligne.trim()) {
      i += 1
      continue
    }
    const titre = /^(#{1,3})\s+(.*)$/.exec(ligne)
    if (titre) {
      resultat.push({ type: 'titre', niveau: titre[1].length, texte: titre[2] })
      i += 1
      continue
    }
    if (/^---+\s*$/.test(ligne)) {
      resultat.push({ type: 'separateur' })
      i += 1
      continue
    }
    if (ligne.trim().startsWith('|')) {
      const tableau = []
      while (i < lignes.length && lignes[i].trim().startsWith('|')) {
        if (!/^\s*\|?\s*-{3,}/.test(lignes[i])) tableau.push(cellules(lignes[i]))
        i += 1
      }
      resultat.push({ type: 'tableau', lignes: tableau })
      continue
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(ligne)) {
      const ordonnee = /^\s*\d+\./.test(ligne)
      const elements = []
      while (i < lignes.length && /^\s*([-*]|\d+\.)\s+/.test(lignes[i])) {
        elements.push(lignes[i].replace(/^\s*([-*]|\d+\.)\s+/, ''))
        i += 1
      }
      resultat.push({ type: 'liste', ordonnee, elements })
      continue
    }
    const paragraphe = []
    while (
      i < lignes.length &&
      lignes[i].trim() &&
      !/^(#{1,3})\s/.test(lignes[i]) &&
      !lignes[i].trim().startsWith('|') &&
      !/^\s*([-*]|\d+\.)\s+/.test(lignes[i])
    ) {
      paragraphe.push(lignes[i])
      i += 1
    }
    resultat.push({ type: 'paragraphe', texte: paragraphe.join(' ') })
  }
  return resultat
}

export default function ApercuMarkdown({ markdown }) {
  return (
    <div className="space-y-3 text-sm text-ink-800">
      {blocs(markdown).map((bloc, i) => {
        if (bloc.type === 'titre') {
          // Les titres du document commencent sous le titre de la fenêtre :
          // un h1 dans une fenêtre casserait la hiérarchie de la page.
          const Balise = bloc.niveau === 1 ? 'h3' : bloc.niveau === 2 ? 'h4' : 'h5'
          const taille = bloc.niveau === 1 ? 'text-lg' : bloc.niveau === 2 ? 'text-base' : 'text-sm'
          return (
            <Balise key={i} className={`font-display font-semibold text-ink-900 ${taille}`}>
              <EnLigne texte={bloc.texte} />
            </Balise>
          )
        }
        if (bloc.type === 'separateur') return <hr key={i} className="border-ink-200" />
        if (bloc.type === 'tableau') {
          const [entete, ...corps] = bloc.lignes
          const enteteVide = entete.every((c) => !c)
          return (
            <div key={i} className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                {!enteteVide && (
                  <thead>
                    <tr>
                      {entete.map((c, j) => (
                        <th key={j} className="border-b border-ink-200 px-2 py-1 text-left font-semibold">
                          <EnLigne texte={c} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {corps.map((ligne, j) => (
                    <tr key={j} className="border-b border-ink-100">
                      {ligne.map((c, k) => (
                        <td key={k} className="px-2 py-1 align-top">
                          <EnLigne texte={c} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
        if (bloc.type === 'liste') {
          const Liste = bloc.ordonnee ? 'ol' : 'ul'
          return (
            <Liste key={i} className={`space-y-1 pl-5 ${bloc.ordonnee ? 'list-decimal' : 'list-disc'}`}>
              {bloc.elements.map((element, j) => (
                <li key={j}>
                  <EnLigne texte={element} />
                </li>
              ))}
            </Liste>
          )
        }
        return (
          <p key={i}>
            <EnLigne texte={bloc.texte} />
          </p>
        )
      })}
    </div>
  )
}
