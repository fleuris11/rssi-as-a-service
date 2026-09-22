/**
 * L'ÉCHELLE DE RISQUE — quatre crans, et une seule définition.
 *
 * Le vocabulaire est celui de la vigilance publique française : quatre
 * niveaux, que tout le monde sait lire sans qu'on les lui explique.
 *
 * Chaque cran porte trois choses, et les trois voyagent ensemble : une
 * COULEUR, un MOT et un GLYPHE. Aucune information du produit ne doit être
 * portée par la couleur seule — ni pour un daltonien, ni sur un PDF en noir
 * et blanc, ni sur un écran mal réglé.
 *
 * Les seuils sont ceux d'ADR-016, que le serveur applique déjà. L'interface
 * ne les recalcule pas : elle traduit le nom que le serveur renvoie, et ne
 * tombe sur le calcul que si le nom manque.
 */

export const CRANS = {
  calme: {
    nom: 'Calme',
    cle: 'calm',
    // Un disque plein : rien ne dépasse.
    glyphe: '●',
    phrase: 'Rien à signaler aujourd’hui.',
    texte: 'text-risk-calm',
    fond: 'bg-risk-calm-surface',
    filet: 'border-risk-calm-border',
    trait: 'var(--color-risk-calm)',
  },
  surveille: {
    nom: 'À surveiller',
    cle: 'watch',
    // Un demi-disque : la moitié de l'attention.
    glyphe: '◐',
    phrase: 'Rien d’urgent, mais deux points méritent un œil cette semaine.',
    texte: 'text-risk-watch',
    fond: 'bg-risk-watch-surface',
    filet: 'border-risk-watch-border',
    trait: 'var(--color-risk-watch)',
  },
  preoccupant: {
    nom: 'Préoccupant',
    cle: 'concern',
    // Un triangle : le panneau de danger.
    glyphe: '▲',
    phrase: 'Quelque chose doit être traité dans les jours qui viennent.',
    texte: 'text-risk-concern',
    fond: 'bg-risk-concern-surface',
    filet: 'border-risk-concern-border',
    trait: 'var(--color-risk-concern)',
  },
  critique: {
    nom: 'Critique',
    cle: 'critical',
    // Un carré plein : l'arrêt.
    glyphe: '■',
    phrase: 'Une action est à mener aujourd’hui.',
    texte: 'text-risk-critical',
    fond: 'bg-risk-critical-surface',
    filet: 'border-risk-critical-border',
    trait: 'var(--color-risk-critical)',
  },
}

export const ORDRE_CRANS = ['calme', 'surveille', 'preoccupant', 'critique']

/** Les noms que le serveur emploie, vers les nôtres. */
const ALIAS = {
  calm: 'calme',
  calme: 'calme',
  watch: 'surveille',
  surveille: 'surveille',
  concern: 'preoccupant',
  preoccupant: 'preoccupant',
  critical: 'critique',
  critique: 'critique',
}

/**
 * Le cran d'un score sur 100. Seuils d'ADR-016 : calme < 20 ≤ à surveiller
 * < 50 ≤ préoccupant < 75 ≤ critique.
 *
 * `niveau` a la priorité sur `score` : c'est le serveur qui décide, le calcul
 * local n'est qu'un repli quand la réponse ne porte pas le nom.
 */
export function cranDe(score, niveau) {
  if (niveau && ALIAS[niveau]) return CRANS[ALIAS[niveau]]
  if (score === null || score === undefined || Number.isNaN(Number(score))) return null
  const valeur = Number(score)
  if (valeur >= 75) return CRANS.critique
  if (valeur >= 50) return CRANS.preoccupant
  if (valeur >= 20) return CRANS.surveille
  return CRANS.calme
}
