/**
 * Regroupe les compromissions par gravité.
 *
 * La liste arrivait à plat, et le serveur ne garantit pas l'ordre par
 * gravité : une fuite critique se retrouvait sous quatre fuites élevées. Sur
 * une page dont l'objet est de dire par quoi commencer, c'est le défaut le
 * plus coûteux — il ne se voit pas, il se paie en temps perdu.
 *
 * L'ordre est celui du produit (critique → élevée → attention), jamais l'ordre
 * d'arrivée. À l'intérieur d'un groupe, l'ordre du serveur est conservé : il
 * porte déjà une logique (date de fuite décroissante).
 *
 * Une gravité inconnue n'est JAMAIS écartée. Le front ne connaît que trois
 * clés ; si le serveur en ajoute une, la faire disparaître de la liste
 * masquerait une fuite réelle — exactement ce que cette page existe pour
 * empêcher. Elle est donc rassemblée sous un groupe nommé, placé en dernier.
 */

export const ORDRE_GRAVITE = ['critical', 'high', 'attention']

const LIBELLE_GRAVITE = {
  critical: 'Critique',
  high: 'Élevée',
  attention: 'Attention',
}

/** Teinte du palier de risque correspondant. Les compromissions parlent
 *  `critical`/`high`/`attention` là où les scores d'exposition parlent
 *  `critique`/`preoccupant`/… : deux vocabulaires serveur distincts, une
 *  seule échelle visuelle. */
export const TEINTE_GRAVITE = {
  critical: 'var(--color-risk-critical)',
  high: 'var(--color-risk-concern)',
  attention: 'var(--color-risk-watch)',
}

export function teinteGravite(severite) {
  return TEINTE_GRAVITE[severite] || 'var(--color-ink-300)'
}

/** « Critique — 4 fuites ». Le compte appartient au séparateur : c'est là
 *  qu'on décide si on lit la suite. */
export function libelleGroupe(severite, nombre) {
  const nom = LIBELLE_GRAVITE[severite] || 'Autre gravité'
  return `${nom} — ${nombre} fuite${nombre > 1 ? 's' : ''}`
}

export function grouperParGravite(findings = []) {
  const paniers = new Map()
  for (const finding of findings) {
    const cle = ORDRE_GRAVITE.includes(finding.severity) ? finding.severity : 'autre'
    if (!paniers.has(cle)) paniers.set(cle, [])
    paniers.get(cle).push(finding)
  }

  const groupes = []
  for (const severite of [...ORDRE_GRAVITE, 'autre']) {
    const items = paniers.get(severite)
    if (!items || items.length === 0) continue
    groupes.push({
      severite,
      libelle: libelleGroupe(severite, items.length),
      teinte: teinteGravite(severite),
      findings: items,
    })
  }
  return groupes
}
