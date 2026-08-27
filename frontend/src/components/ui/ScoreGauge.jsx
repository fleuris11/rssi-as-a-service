/**
 * Jauge de score — un composant, deux échelles, et le SENS toujours écrit.
 *
 * ## Le défaut que ce composant répare
 *
 * Le produit affichait deux anneaux, de même forme et de même taille, dont
 * les échelles étaient **inverses** :
 *
 * - maturité ANSSI (tableau de bord, résultats) : 80 est un bon score, vert ;
 * - exposition (page Exposition) : 80 est un mauvais score, rouge.
 *
 * Rien à l'écran ne prévenait. Un dirigeant qui voit 80 en vert sur un écran
 * et 80 en rouge sur le suivant n'a aucun moyen de savoir lequel le rassure.
 * En démonstration, cela peut lui faire dire l'inverse de la réalité.
 *
 * Ce n'est pas un défaut de style : c'est un défaut de sens. D'où la règle
 * posée ici — **une jauge dit toujours dans quel sens elle se lit**, et le
 * dit en toutes lettres, pas seulement par sa couleur.
 *
 * ## L'échelle de gravité
 *
 * Les couleurs viennent de la famille `risk-*`, alignée sur les seuils
 * d'ADR-016 (calme < 20 <= à surveiller < 50 <= préoccupant < 75 <=
 * critique) — jamais de `accent`, qui est la couleur des actions.
 *
 * La couleur n'est jamais le seul porteur d'information : le niveau est
 * toujours écrit à côté du chiffre.
 *
 * ## Le niveau vient du serveur
 *
 * Quand l'appelant fournit `level` (la clé renvoyée par l'API), c'est elle
 * qui décide de la teinte — jamais un recalcul à partir du score. Les seuils
 * vivent dans les réglages Django (ADR-016) : les redériver ici ferait qu'un
 * ajustement de seuil côté serveur ne se verrait pas à l'écran. Le calcul
 * local n'est qu'un repli, pour les scores qui n'ont pas de niveau serveur
 * (la maturité ANSSI).
 */

// Correspondance entre les clés de niveau du serveur et notre échelle de
// teintes. Une clé inconnue (niveau ajouté côté serveur, non encore connu de
// l'interface) retombe sur un rendu neutre plutôt que de casser la page.
const CLE_SERVEUR_VERS_RISQUE = {
  calme: 'calm',
  a_surveiller: 'watch',
  preoccupant: 'concern',
  critique: 'critical',
}

const NIVEAUX_EXPOSITION = [
  { max: 20, cle: 'calm', libelle: 'Calme' },
  { max: 50, cle: 'watch', libelle: 'À surveiller' },
  { max: 75, cle: 'concern', libelle: 'Préoccupant' },
  { max: Infinity, cle: 'critical', libelle: 'Critique' },
]

// Maturité : l'échelle est inversée (haut = bon), d'où des bornes lues
// depuis le haut. Les deux tables vivent côte à côte volontairement — c'est
// leur voisinage qui rend l'inversion visible en lecture de code.
const NIVEAUX_MATURITE = [
  { max: 40, cle: 'critical', libelle: 'À renforcer' },
  { max: 60, cle: 'concern', libelle: 'En progression' },
  { max: 80, cle: 'watch', libelle: 'Correct' },
  { max: Infinity, cle: 'calm', libelle: 'Solide' },
]

const TEINTES = {
  calm: 'var(--color-risk-calm)',
  watch: 'var(--color-risk-watch)',
  concern: 'var(--color-risk-concern)',
  critical: 'var(--color-risk-critical)',
}

export const SENS = {
  // « Plus c'est haut, plus le risque est grand. »
  exposure: {
    niveaux: NIVEAUX_EXPOSITION,
    legende: 'plus le chiffre est haut, plus le risque est élevé',
  },
  // « Plus c'est haut, mieux c'est. »
  maturity: {
    niveaux: NIVEAUX_MATURITE,
    legende: 'plus le chiffre est haut, meilleure est la maturité',
  },
}

/** Teinte d'un niveau serveur, pour les éléments qui entourent la jauge
 *  (filet de carte, pastille). Une seule table de correspondance dans tout
 *  le produit : une carte et sa jauge ne peuvent pas diverger. */
export function teinteRisque(level) {
  const cle = CLE_SERVEUR_VERS_RISQUE[level]
  return cle ? TEINTES[cle] : 'var(--color-ink-300)'
}

export function niveauPour(score, scale = 'exposure') {
  const { niveaux } = SENS[scale] || SENS.exposure
  return niveaux.find((n) => score < n.max) || niveaux[niveaux.length - 1]
}

/**
 * @param {number|null} score        0-100, ou null si indisponible
 * @param {'exposure'|'maturity'} scale  sens de lecture
 * @param {string} [level]           clé de niveau du serveur — fait autorité
 * @param {string} [levelLabel]      libellé du serveur, prioritaire sur le nôtre
 * @param {'sm'|'md'|'lg'} size
 * @param {boolean} [showLegend]     affiche la phrase de sens sous la jauge
 */
export default function ScoreGauge({
  score,
  scale = 'exposure',
  level,
  levelLabel,
  size = 'md',
  showLegend = false,
  className = '',
}) {
  const indisponible = score === null || score === undefined
  const valeur = indisponible ? 0 : Math.max(0, Math.min(100, score))
  // Le niveau du serveur fait autorité ; le calcul local n'est qu'un repli.
  const cleRisque = level ? CLE_SERVEUR_VERS_RISQUE[level] : undefined
  const niveau = indisponible ? null : niveauPour(valeur, scale)
  const teinte = indisponible
    ? 'var(--color-ink-300)'
    : (TEINTES[cleRisque] ?? (level ? 'var(--color-ink-500)' : TEINTES[niveau.cle]))
  const libelle = levelLabel || (level ? undefined : niveau?.libelle)
  const { legende } = SENS[scale] || SENS.exposure

  const DIM = { sm: 56, md: 88, lg: 128 }[size] || 88
  const EPAISSEUR = { sm: 5, md: 7, lg: 10 }[size] || 7
  const rayon = (DIM - EPAISSEUR) / 2
  const circonference = 2 * Math.PI * rayon
  const reste = circonference * (1 - valeur / 100)

  const tailleChiffre = { sm: 'text-lg', md: 'text-3xl', lg: 'text-5xl' }[size] || 'text-3xl'

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className="relative shrink-0" style={{ width: DIM, height: DIM }}>
        <svg
          width={DIM}
          height={DIM}
          viewBox={`0 0 ${DIM} ${DIM}`}
          className="-rotate-90"
          aria-hidden="true"
        >
          <circle
            cx={DIM / 2}
            cy={DIM / 2}
            r={rayon}
            fill="none"
            stroke="var(--color-ink-100)"
            strokeWidth={EPAISSEUR}
          />
          <circle
            cx={DIM / 2}
            cy={DIM / 2}
            r={rayon}
            fill="none"
            stroke={teinte}
            strokeWidth={EPAISSEUR}
            strokeLinecap="round"
            strokeDasharray={circonference}
            strokeDashoffset={reste}
            // Le remplissage s'anime une fois au montage. Le CHIFFRE, lui,
            // est écrit dans le DOM sans condition : aucun contenu ne dépend
            // du déclenchement d'une animation pour être lisible.
            className="motion-safe:[transition:stroke-dashoffset_700ms_cubic-bezier(0.4,0,0.2,1)]"
          />
        </svg>
        <span
          className={`absolute inset-0 flex items-center justify-center font-display font-semibold text-ink-900 ${tailleChiffre}`}
        >
          {indisponible ? '—' : Math.round(valeur)}
        </span>
      </div>

      <div className="min-w-0">
        {libelle && (
          <p className="font-medium" style={{ color: teinte }}>
            {libelle}
          </p>
        )}
        {/* Le sens de lecture, en toutes lettres. C'est la raison d'être de
            ce composant : sans cette ligne, deux anneaux identiques
            portaient deux échelles opposées sans le dire. */}
        {showLegend && <p className="t-meta mt-0.5">Sur 100 — {legende}.</p>}
      </div>
    </div>
  )
}
