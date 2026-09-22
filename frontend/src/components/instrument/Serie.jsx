import { useId, useMemo, useState } from 'react'

/**
 * SÉRIE TEMPORELLE AVEC CURSEUR « MAINTENANT » — l'interaction signature du
 * produit (docs/design.md § « L'interaction signature »).
 *
 * Une ligne verticale marque un instant ; sa valeur se lit au-dessus, en
 * chiffres mesurés. Elle suit la souris ET le clavier (flèches gauche/droite,
 * Origine/Fin), parce qu'une donnée qu'on ne peut lire qu'à la souris n'est
 * pas lisible.
 *
 * Dessinée en SVG plutôt qu'avec recharts : le produit charge déjà recharts
 * pour les graphiques du tableau de bord, mais une série de quatre-vingt-dix
 * points avec un curseur n'a besoin que d'un `<path>`. Sur la vitrine, qui ne
 * doit rien charger d'autre que l'essentiel, c'est trente lignes contre cent
 * kilo-octets.
 *
 * Le tracé est rendu ENTIER dès le premier rendu. L'animation d'entrée ne
 * fait que redessiner ce qui est déjà là.
 */

const LARGEUR = 600
const HAUTEUR = 160
const MARGE_HAUTE = 22
const MARGE_BASSE = 18

export default function Serie({
  points = [],
  legende = 'Évolution',
  unite = '',
  couleur = 'var(--color-brand-600)',
  className = '',
}) {
  const identifiant = useId()
  const [indice, setIndice] = useState(null)

  const { chemin, aire, min, max, coordonnees } = useMemo(() => {
    if (points.length < 2) return { chemin: '', aire: '', min: 0, max: 0, coordonnees: [] }
    const valeurs = points.map((p) => Number(p.valeur))
    const bas = Math.min(...valeurs)
    const haut = Math.max(...valeurs)
    // Une série plate ne doit pas diviser par zéro ni se coller au bord.
    const etendue = haut - bas || 1
    const utile = HAUTEUR - MARGE_HAUTE - MARGE_BASSE

    const coords = points.map((point, rang) => ({
      x: (rang / (points.length - 1)) * LARGEUR,
      y: MARGE_HAUTE + utile - ((Number(point.valeur) - bas) / etendue) * utile,
      point,
    }))

    const trace = coords.map((c, rang) => `${rang === 0 ? 'M' : 'L'}${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(' ')
    return {
      chemin: trace,
      aire: `${trace} L${LARGEUR} ${HAUTEUR} L0 ${HAUTEUR} Z`,
      min: bas,
      max: haut,
      coordonnees: coords,
    }
  }, [points])

  if (points.length < 2) {
    return (
      <p className={`t-meta ${className}`}>
        Pas encore assez de mesures pour tracer une évolution.
      </p>
    )
  }

  const rangCourant = indice === null ? coordonnees.length - 1 : indice
  const courant = coordonnees[rangCourant]

  const deplacer = (evenement) => {
    const cadre = evenement.currentTarget.getBoundingClientRect()
    const ratio = (evenement.clientX - cadre.left) / cadre.width
    setIndice(Math.max(0, Math.min(coordonnees.length - 1, Math.round(ratio * (coordonnees.length - 1)))))
  }

  const auClavier = (evenement) => {
    const pas = { ArrowLeft: -1, ArrowRight: 1 }[evenement.key]
    if (pas) {
      evenement.preventDefault()
      setIndice(Math.max(0, Math.min(coordonnees.length - 1, rangCourant + pas)))
      return
    }
    if (evenement.key === 'Home') {
      evenement.preventDefault()
      setIndice(0)
    }
    if (evenement.key === 'End') {
      evenement.preventDefault()
      setIndice(coordonnees.length - 1)
    }
  }

  const valeurLue = `${Number(courant.point.valeur).toLocaleString('fr-FR')}${unite}`

  return (
    <figure className={className}>
      <figcaption className="flex items-baseline justify-between gap-3">
        <span className="t-legende">{legende}</span>
        <span className="n text-sm text-ink-900">
          {valeurLue}
          <span className="t-meta ml-2 font-sans">{courant.point.libelle}</span>
        </span>
      </figcaption>

      <svg
        viewBox={`0 0 ${LARGEUR} ${HAUTEUR}`}
        preserveAspectRatio="none"
        className="mt-2 h-28 w-full cursor-crosshair touch-none sm:h-36"
        role="img"
        aria-describedby={identifiant}
        tabIndex={0}
        onMouseMove={deplacer}
        onMouseLeave={() => setIndice(null)}
        onKeyDown={auClavier}
      >
        <defs>
          <linearGradient id={`voile-${identifiant}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={couleur} stopOpacity="0.16" />
            <stop offset="100%" stopColor={couleur} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* La réglure : la face d'instrument est réglée, pas vide. */}
        {[0, 0.5, 1].map((part) => (
          <line
            key={part}
            x1="0"
            x2={LARGEUR}
            y1={MARGE_HAUTE + part * (HAUTEUR - MARGE_HAUTE - MARGE_BASSE)}
            y2={MARGE_HAUTE + part * (HAUTEUR - MARGE_HAUTE - MARGE_BASSE)}
            stroke="var(--color-ink-200)"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
        ))}

        <path d={aire} fill={`url(#voile-${identifiant})`} />
        <path
          d={chemin}
          fill="none"
          stroke={couleur}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />

        {/* Le curseur « maintenant ». Seul élément qui porte la couleur
            d'action : la couleur est confinée à l'élément vivant. */}
        <line
          x1={courant.x}
          x2={courant.x}
          y1={MARGE_HAUTE - 8}
          y2={HAUTEUR - MARGE_BASSE}
          stroke="var(--color-ink-900)"
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
        />
        <circle cx={courant.x} cy={courant.y} r="3.5" fill="var(--color-surface)" stroke={couleur} strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>

      <p id={identifiant} className="lecture-seule">
        {legende} : {points.length} mesures, de {points[0].libelle} à{' '}
        {points[points.length - 1].libelle}. Minimum {min}
        {unite}, maximum {max}
        {unite}. Valeur au curseur : {valeurLue} le {courant.point.libelle}. Utilisez les flèches
        gauche et droite pour parcourir la série.
      </p>
    </figure>
  )
}
