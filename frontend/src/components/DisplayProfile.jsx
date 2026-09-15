import { ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { useDisplayProfile } from '../context/useDisplayProfile'
import { niveauPour } from './ui/ScoreGauge'

/**
 * Les primitives du profil d'affichage (V2-5, ADR-031 ; étendues au lot C).
 *
 * La règle qu'elles font respecter : **le contenu ne change jamais, seule sa
 * présentation change**. Un détail technique reste dans le DOM dans les deux
 * profils — il est replié en profil dirigeant, déplié en profil technique.
 * Rien n'est retiré, rien n'est réécrit : un même fait reste le même fait, et
 * un dirigeant qui déplie voit exactement ce que voit son prestataire.
 *
 * C'est aussi pour cela que ce sont des composants d'affichage et non des
 * conditions `if (isTechnical)` disséminées : une condition finit toujours
 * par supprimer quelque chose.
 *
 * Lot C : l'interrupteur existait, mais ces primitives n'étaient posées que
 * sur deux écrans. Partout ailleurs, basculer ne changeait strictement rien —
 * et un interrupteur qui ne fait rien retire sa crédibilité à tout le reste.
 */

export function TechnicalDetail({ summary = 'Détail technique', children, className = '' }) {
  const { isTechnical } = useDisplayProfile()
  const [open, setOpen] = useState(isTechnical)

  const Icone = open ? ChevronDown : ChevronRight
  return (
    <div className={`mt-2 ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="transition-smooth flex items-center gap-1 text-xs text-ink-500 hover:text-brand-600"
      >
        <Icone className="size-3.5" aria-hidden="true" />
        {summary}
      </button>
      {/* `hidden` plutôt qu'un rendu conditionnel : le contenu existe dans la
          page quel que soit le profil, il est seulement masqué. Un lecteur
          d'écran et une recherche dans la page le retrouvent. */}
      <div hidden={!open} className="mt-2 rounded-md border border-ink-200 bg-canvas p-3 text-xs">
        {children}
      </div>
    </div>
  )
}

/**
 * Un terme technique et sa traduction. En profil dirigeant on lit la
 * traduction, le terme technique suit entre parenthèses ; en profil technique
 * c'est l'inverse.
 *
 * Les deux sont toujours affichés. Masquer le terme technique au dirigeant
 * l'empêcherait de le reconnaître dans le courriel de son prestataire — or
 * c'est précisément le moment où il en a besoin.
 */
export function Term({ code, plain, className = '' }) {
  const { isTechnical } = useDisplayProfile()
  const [devant, derriere] = isTechnical ? [code, plain] : [plain, code]
  return (
    <span className={className}>
      {devant} <span className="text-ink-500">({derriere})</span>
    </span>
  )
}

/**
 * Un bloc d'explication. Toujours présent, mais discret en profil technique :
 * la consigne demande que les explications « restent mais ne prennent pas
 * toute la place ».
 */
export function Explanation({ children, className = '' }) {
  const { isTechnical } = useDisplayProfile()
  if (isTechnical) {
    return <p className={`mt-1 text-xs text-ink-500 ${className}`}>{children}</p>
  }
  return (
    <p className={`mt-2 rounded-md bg-brand-50 px-3 py-2 text-sm text-ink-600 ${className}`}>
      {children}
    </p>
  )
}

const MOIS = { day: 'numeric', month: 'long', year: 'numeric' }

/** Le fuseau n'est pas un détail pour un technicien : un horodatage sans
 *  fuseau se lit de travers dès qu'on le recoupe avec un journal serveur. */
function horodatagePrecis(date) {
  const deux = (n) => String(n).padStart(2, '0')
  const decalage = -date.getTimezoneOffset()
  const signe = decalage >= 0 ? '+' : '-'
  const heures = deux(Math.floor(Math.abs(decalage) / 60))
  const minutes = deux(Math.abs(decalage) % 60)
  return (
    `${date.getFullYear()}-${deux(date.getMonth() + 1)}-${deux(date.getDate())} ` +
    `${deux(date.getHours())}:${deux(date.getMinutes())}:${deux(date.getSeconds())} ` +
    `UTC${signe}${heures}:${minutes}`
  )
}

/**
 * Une date. Le dirigeant lit « 12 septembre 2026 » ; le technicien lit
 * l'horodatage complet, à la seconde, avec son fuseau.
 *
 * Même instant dans les deux cas : `dateTime` porte la valeur exacte, et le
 * libellé du dirigeant la garde en infobulle. On change la précision de la
 * lecture, jamais le fait.
 */
export function ProfileDate({ value, fallback = 'date inconnue', dateOnly = false }) {
  const { isTechnical } = useDisplayProfile()
  if (!value) return <span>{fallback}</span>
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return <span>{fallback}</span>
  const precis = horodatagePrecis(date)
  // Une date sans heure (date de fuite, échéance) n'a pas de seconde à
  // montrer : l'afficher « à 00:00:00 » inventerait une précision.
  const lecture = isTechnical
    ? dateOnly
      ? precis.slice(0, 10)
      : precis
    : date.toLocaleDateString('fr-FR', MOIS)
  return (
    <time dateTime={date.toISOString()} title={isTechnical ? undefined : precis}>
      {lecture}
    </time>
  )
}

/**
 * Une valeur brute : identifiant interne, code source, empreinte.
 *
 * En profil technique elle est affichée, en police à chasse fixe. En profil
 * dirigeant elle reste dans la page mais masquée : elle ne dit rien à qui ne
 * la manipule pas, et elle reste retrouvable dès qu'on bascule.
 */
export function TechnicalValue({ label, value, className = '' }) {
  const { isTechnical } = useDisplayProfile()
  if (value === null || value === undefined || value === '') return null
  return (
    <span hidden={!isTechnical} className={`font-mono text-xs text-ink-600 ${className}`}>
      {label ? `${label} ` : ''}
      {value}
    </span>
  )
}

/** Ce que veut dire un score, en une phrase. Les seuils viennent de la même
 *  table que la jauge : un chiffre et sa phrase ne peuvent pas diverger. */
const PHRASES = {
  maturity: {
    calm: 'votre niveau est solide',
    watch: 'votre niveau est correct, des points restent à consolider',
    concern: 'votre niveau progresse, mais reste insuffisant',
    critical: 'votre niveau est à renforcer en priorité',
  },
  exposure: {
    calm: 'votre exposition est faible',
    watch: 'votre exposition est à surveiller',
    concern: 'votre exposition est préoccupante',
    critical: 'votre exposition est critique, une action est attendue',
  },
}

export function lectureDuScore(score, scale = 'maturity') {
  if (score === null || score === undefined) return null
  const niveau = niveauPour(score, scale)
  return PHRASES[scale]?.[niveau.cle] ?? null
}

/**
 * Un score et son sens.
 *
 * Dirigeant : « 92 sur 100 — votre niveau est solide ». Technicien :
 * « 92/100 », la phrase en retrait. La phrase est dans la page dans les deux
 * cas : c'est la même lecture, plus ou moins mise en avant.
 */
export function ScoreReading({ score, scale = 'maturity', className = '' }) {
  const { isTechnical } = useDisplayProfile()
  if (score === null || score === undefined) {
    return <span className={className}>non mesuré</span>
  }
  const valeur = String(score).replace('.', ',')
  const phrase = lectureDuScore(score, scale)
  if (isTechnical) {
    return (
      <span className={className}>
        <span className="font-medium tabular-nums">{valeur}/100</span>
        {phrase && <span className="ml-1 text-xs text-ink-500">({phrase})</span>}
      </span>
    )
  }
  return (
    <span className={className}>
      <span className="font-medium">{valeur} sur 100</span>
      {phrase && <span> — {phrase}</span>}
    </span>
  )
}

/**
 * L'ordre de lecture d'une alerte ou d'une fuite.
 *
 * Dirigeant : l'impact, puis l'action, puis le constat technique replié —
 * « ce que ça me fait, ce que je dois faire » avant « ce que la machine a vu ».
 * Technicien : le constat technique déplié en tête, l'impact et l'action
 * resserrés dessous.
 *
 * Mêmes trois blocs, même texte : seuls l'ordre et le poids changent.
 */
export function AlertReading({ meaning, action, detail, detailSummary = 'Ce qui a été constaté' }) {
  const { isTechnical } = useDisplayProfile()

  const impact = meaning ? (
    <p
      key="impact"
      className={
        isTechnical
          ? 'mt-1 text-xs text-ink-500'
          : 'mt-2 rounded-md bg-ink-50 px-3 py-2 text-sm text-ink-700'
      }
    >
      <span className="font-semibold">Ce que ça implique : </span>
      {meaning}
    </p>
  ) : null

  const aFaire = action ? (
    <p
      key="action"
      className={
        isTechnical
          ? 'mt-1 text-xs text-ink-600'
          : 'mt-2 rounded-md bg-accent-100/50 px-3 py-2 text-sm text-accent-900'
      }
    >
      <span className="font-semibold">À faire : </span>
      {action}
    </p>
  ) : null

  const constat = detail ? (
    <TechnicalDetail key="detail" summary={detailSummary}>
      {detail}
    </TechnicalDetail>
  ) : null

  return (
    <div data-lecture={isTechnical ? 'technique' : 'dirigeant'}>
      {isTechnical ? [constat, impact, aFaire] : [impact, aFaire, constat]}
    </div>
  )
}
