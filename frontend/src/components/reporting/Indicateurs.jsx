import { ArrowRight, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import Card, { CardHeader } from '../ui/Card'

/**
 * Les briques communes du tableau de bord et de la page Rapports (lot C).
 *
 * Elles vivaient dans la seule page Rapports (V2-3). Le tableau de bord en a
 * besoin à son tour ; deux copies du même sélecteur de période ou de la même
 * flèche de tendance auraient fini par ne plus dire la même chose — et c'est
 * exactement l'écart qu'un comité remarque.
 */

/* Les series de graphique prennent une couleur en PROPRIETE et ne peuvent pas
   porter une classe Tailwind. Elles lisent donc le jeton directement : une
   variable CSS est une valeur SVG valide, et la couleur reste ainsi dans
   tokens.css comme partout ailleurs (garde : src/jetons.test.js). */
export const COULEUR_TRAIT = 'var(--color-brand-600)'
export const COULEUR_SECONDE = 'var(--color-risk-calm)'

export function formatJour(valeur) {
  if (!valeur) return '—'
  return new Date(valeur).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
}

export function formatNombre(valeur, suffixe = '') {
  if (valeur === null || valeur === undefined) return 'non mesuré'
  return `${String(valeur).replace('.', ',')}${suffixe}`
}

/**
 * L'écart par rapport au point de comparaison.
 *
 * Le SENS vient du serveur (`is_improvement`) et n'est pas déduit du signe :
 * une baisse est une bonne nouvelle pour les fuites et une mauvaise pour la
 * maturité. Une flèche verte sur « fuites en hausse » est le genre d'erreur
 * qu'on ne voit qu'en comité.
 */
export function Evolution({ evolution, suffixe = '' }) {
  if (!evolution || evolution.delta === null || evolution.delta === undefined) {
    return <span className="t-meta">pas de point de comparaison</span>
  }
  if (evolution.direction === 'stable') {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-ink-500">
        <Minus className="size-3.5" aria-hidden="true" />
        stable
      </span>
    )
  }
  const Fleche = evolution.direction === 'hausse' ? TrendingUp : TrendingDown
  const teinte =
    evolution.is_improvement === true
      ? 'text-ok-strong'
      : evolution.is_improvement === false
        ? 'text-critical-strong'
        : 'text-ink-500'
  const lecture =
    evolution.is_improvement === true
      ? 'amélioration'
      : evolution.is_improvement === false
        ? 'dégradation'
        : 'évolution'
  return (
    <span
      className={`inline-flex items-center gap-1 text-sm ${teinte}`}
      // Exposé pour que les tests vérifient le SENS lu, et non la couleur
      // obtenue : une classe change au premier ajustement de charte.
      data-improvement={String(evolution.is_improvement)}
    >
      <Fleche className="size-3.5" aria-hidden="true" />
      {evolution.direction === 'hausse' ? '+' : '−'}
      {formatNombre(Math.abs(evolution.delta), suffixe)}
      {/* La couleur ne porte jamais seule l'information. */}
      <span className="sr-only"> ({lecture})</span>
    </span>
  )
}

/**
 * Un indicateur : la valeur, la tendance, ce qu'il veut dire — et le lien vers
 * l'écran où l'on agit (lot C, point 7). Un chiffre sans chemin vers le
 * détail oblige le RSSI à chercher dans le menu ce qui se cache derrière.
 */
export function Indicateur({ titre, valeur, quoi, evolution, suffixe, lien, libelleLien }) {
  return (
    <Card padding="p-4" className="flex flex-col">
      <p className="t-legende">{titre}</p>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-display text-3xl font-semibold text-ink-900">{valeur}</span>
        <Evolution evolution={evolution} suffixe={suffixe} />
      </div>
      <p className="mt-2 flex-1 text-xs text-ink-500">{quoi}</p>
      {lien && (
        <Link
          to={lien}
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          {libelleLien}
          <ArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      )}
    </Card>
  )
}

export function SelecteurDePeriode({ periodes, courante, onChange, personnalisee, onPersonnalisee }) {
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Période">
      {periodes.map((p) => (
        <button
          key={p.key}
          type="button"
          onClick={() => onChange(p.key)}
          aria-pressed={courante === p.key}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-smooth ${
            courante === p.key ? 'bg-brand-600 text-white' : 'bg-ink-50 text-ink-600 hover:bg-ink-100'
          }`}
        >
          {p.label}
        </button>
      ))}
      {courante === 'custom' && (
        <span className="flex flex-wrap items-center gap-2 text-sm text-ink-600">
          <input
            type="date"
            value={personnalisee.start}
            onChange={(e) => onPersonnalisee({ ...personnalisee, start: e.target.value })}
            className="rounded-md border border-ink-200 px-2 py-1 text-sm"
            aria-label="Date de début"
          />
          <span>au</span>
          <input
            type="date"
            value={personnalisee.end}
            onChange={(e) => onPersonnalisee({ ...personnalisee, end: e.target.value })}
            className="rounded-md border border-ink-200 px-2 py-1 text-sm"
            aria-label="Date de fin"
          />
        </span>
      )}
    </div>
  )
}

/**
 * Une courbe, et la question à laquelle elle répond.
 *
 * Lot C, point 10 : « si tu ne peux pas formuler la question, ne fais pas le
 * graphique ». La question est donc un paramètre OBLIGATOIRE, et elle est le
 * sous-titre de la carte. La lecture est aussi écrite en toutes lettres
 * (`lecture`) : un lecteur d'écran ne voit pas une pente, et un dirigeant
 * pressé non plus.
 */
export function Courbe({ titre, question, lecture, donnees, traits, domaineY, formatY, vide }) {
  if (!question) throw new Error('Une courbe sans question n’a rien à faire à l’écran.')
  const points = (donnees || []).map((p) => ({ ...p, libelle: formatJour(p.date) }))

  return (
    <Card>
      <CardHeader title={titre} subtitle={question} />
      {points.length < 2 ? (
        <p className="text-sm text-ink-500">{vide}</p>
      ) : (
        <>
          {/* Le trace est masque aux technologies d'assistance : la phrase de
              lecture, juste en dessous, dit la meme chose en francais, et un
              SVG de courbe ne s'ecoute pas. Mais recharts pose `tabindex=0`
              sur sa surface : un element focalisable dans un sous-arbre
              `aria-hidden` est une violation « serious » — le clavier peut
              atteindre ce que le lecteur d'ecran ne voit pas.
              `accessibilityLayer={false}` retire ce point d'arret. */}
          <div className="h-56 w-full" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={points}
                accessibilityLayer={false}
                tabIndex={-1}
                margin={{ top: 8, right: 8, bottom: 0, left: -20 }}
              >
                <CartesianGrid stroke="var(--color-ink-100)" vertical={false} />
                <XAxis
                  dataKey="libelle"
                  tick={{ fontSize: 11, fill: 'var(--color-ink-500)' }}
                  interval="preserveStartEnd"
                  minTickGap={40}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: 'var(--color-ink-500)' }}
                  allowDecimals={false}
                  width={48}
                  domain={domaineY}
                  tickFormatter={formatY}
                />
                <Tooltip contentStyle={{ fontSize: 12 }} labelFormatter={(l) => `Le ${l}`} />
                {traits.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
                {traits.map((trait) => (
                  <Line
                    key={trait.cle}
                    type="monotone"
                    dataKey={trait.cle}
                    name={trait.nom}
                    stroke={trait.couleur}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          {lecture && <p className="mt-2 text-sm text-ink-700">{lecture}</p>}
        </>
      )}
    </Card>
  )
}
