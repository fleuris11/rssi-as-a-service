import { Download, FileText } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { reportingApi } from '../api/endpoints'
import {
  COULEUR_TRAIT,
  formatJour,
  formatNombre,
  Indicateur,
  SelecteurDePeriode,
} from '../components/reporting/Indicateurs'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card, { CardHeader } from '../components/ui/Card'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'
import { useAuth } from '../context/AuthContext'

// Lot C : l'indicateur, sa tendance et le sélecteur de période vivent dans
// `components/reporting/Indicateurs.jsx`, partagés avec le tableau de bord.
// Deux copies auraient fini par ne plus lire l'évolution dans le même sens.

/**
 * Le stock de compromissions ouvertes, jour par jour.
 *
 * La question à laquelle ce graphique répond, et la seule : **est-ce que le
 * stock baisse ?** C'est ce qu'un comité demande, et c'est ce qu'un chiffre
 * isolé ne peut pas dire — 14 fuites ouvertes est une bonne nouvelle si on
 * partait de 40, une mauvaise si on partait de 3.
 *
 * Une seule courbe, pas de découpage par gravité : trois courbes
 * répondraient à une question que personne ne pose en comité, et rendraient
 * la première illisible.
 */
function CourbeDesOuvertes({ serie }) {
  if (!serie?.length) return null
  const donnees = serie.map((point) => ({ ...point, label: formatJour(point.date) }))

  return (
    <Card>
      <CardHeader
        title="Compromissions ouvertes"
        subtitle="Le stock à traiter, jour après jour. La question : est-ce qu'il baisse ?"
      />
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={donnees} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid stroke="var(--color-ink-100)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: 'var(--color-ink-500)' }}
              interval="preserveStartEnd"
              minTickGap={40}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--color-ink-500)' }}
              allowDecimals={false}
              width={48}
            />
            <Tooltip
              formatter={(v) => [`${v} ouverte${v > 1 ? 's' : ''}`, '']}
              labelFormatter={(l) => `Le ${l}`}
              contentStyle={{ fontSize: 12 }}
            />
            <Line
              type="monotone"
              dataKey="open"
              stroke={COULEUR_TRAIT}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

/**
 * Où le risque est concentré.
 *
 * La question : **sur quel actif faut-il agir en premier ?** Un tableau et
 * non un graphique — avec trois à dix actifs, une barre horizontale
 * n'apporte rien qu'un nombre aligné ne dise déjà, et coûte un rendu.
 */
function ExpositionParActif({ actifs }) {
  if (!actifs?.length) return null
  const maximum = Math.max(...actifs.map((a) => a.score), 1)

  return (
    <Card>
      <CardHeader
        title="Exposition par actif"
        subtitle="Sur quel actif faut-il agir en premier ?"
      />
      <ul className="space-y-3">
        {actifs.map((actif) => (
          <li key={actif.asset_id}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="truncate text-sm text-ink-800">{actif.asset_value}</span>
              <span className="shrink-0 text-sm text-ink-600">
                {actif.score} — {actif.findings_count} fuite
                {actif.findings_count > 1 ? 's' : ''}
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-ink-100">
              <div
                className="h-1.5 rounded-full bg-brand-600"
                style={{ width: `${Math.round((100 * actif.score) / maximum)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function ReportingPage() {
  const { showToast } = useToast()
  const { currentTenant } = useAuth()
  const [periode, setPeriode] = useState('quarter')
  const [personnalisee, setPersonnalisee] = useState({ start: '', end: '' })
  const [donnees, setDonnees] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [telechargement, setTelechargement] = useState(null)

  const charger = useCallback(async () => {
    setChargement(true)
    try {
      const params =
        periode === 'custom'
          ? { period: 'custom', start: personnalisee.start, end: personnalisee.end }
          : { period: periode }
      const reponse = await reportingApi.dashboard(params)
      setDonnees(reponse.data)
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de charger les indicateurs.',
      })
    } finally {
      setChargement(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periode, personnalisee.start, personnalisee.end])

  useEffect(() => {
    if (periode === 'custom' && (!personnalisee.start || !personnalisee.end)) return
    charger()
  }, [charger, periode, personnalisee.start, personnalisee.end])

  async function telecharger(format) {
    setTelechargement(format)
    try {
      const params =
        periode === 'custom'
          ? { period: 'custom', start: personnalisee.start, end: personnalisee.end }
          : { period: periode }
      const reponse =
        format === 'pdf'
          ? await reportingApi.reportPdf(params)
          : await reportingApi.exportCsv(params)
      // Le nom du fichier vient du serveur : c'est lui qui connaît la période
      // et le nom du client, et deux façons de le composer finiraient par
      // produire deux noms différents pour le même export.
      const entete = reponse.headers['content-disposition'] || ''
      const nom = /filename="([^"]+)"/.exec(entete)?.[1] || `rapport.${format}`
      const url = URL.createObjectURL(new Blob([reponse.data]))
      const lien = document.createElement('a')
      lien.href = url
      lien.download = nom
      lien.click()
      URL.revokeObjectURL(url)
    } catch {
      showToast({
        type: 'error',
        message:
          format === 'pdf'
            ? 'Le document n’a pas pu être produit. Les mêmes chiffres restent exportables en tableur.'
            : 'L’export n’a pas pu être produit.',
      })
    } finally {
      setTelechargement(null)
    }
  }

  if (chargement && !donnees) {
    return (
      <div className="space-y-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }
  if (!donnees) return null

  const { exposure, action_plan: plan, maturity, monitoring, period } = donnees

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-900">
            Rapport de sécurité
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Les chiffres à présenter en comité, sur la période de votre choix. Comparaison à la
            période précédente affichée par défaut.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            icon={Download}
            disabled={telechargement !== null}
            onClick={() => telecharger('csv')}
          >
            Tableur
          </Button>
          <Button
            icon={FileText}
            disabled={telechargement !== null}
            onClick={() => telecharger('pdf')}
          >
            {telechargement === 'pdf' ? 'Génération…' : 'Rapport PDF'}
          </Button>
        </div>
      </div>

      <SelecteurDePeriode
        periodes={donnees.available_periods}
        courante={periode}
        onChange={setPeriode}
        personnalisee={personnalisee}
        onPersonnalisee={setPersonnalisee}
      />
      <p className="t-meta">
        Du {formatJour(period.start)} au {formatJour(period.end)} — {period.days} jours.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Indicateur
          titre="Compromissions ouvertes"
          valeur={exposure.open_total}
          quoi="Données de votre entreprise retrouvées en circulation et non encore traitées."
          evolution={exposure.open_evolution}
        />
        <Indicateur
          titre="Score d'exposition"
          valeur={`${exposure.exposure_score}/100`}
          quoi="Gravité, fraîcheur et exploitabilité des fuites ouvertes. Plus bas est mieux."
          evolution={exposure.evolution}
        />
        <Indicateur
          titre="Score de maturité"
          valeur={maturity.score === null ? 'non mesuré' : `${formatNombre(maturity.score)}/100`}
          quoi="Réponses au référentiel de l'ANSSI. Mesure votre organisation, pas les fuites."
          evolution={maturity.evolution}
          suffixe=" pts"
        />
        <Indicateur
          titre="Disponibilité"
          valeur={formatNombre(monitoring.uptime_percentage, ' %')}
          quoi="Part du temps où vos sites surveillés ont répondu normalement."
          evolution={monitoring.uptime_evolution}
          suffixe=" pts"
        />
      </div>

      {/* Deux mesures, jamais une moyenne des deux (ADR-028). Le dire à
          l'écran évite qu'on la fabrique dans le tableur d'à côté. */}
      <p className="t-meta">
        Le score d’exposition et le score de maturité ne s’additionnent pas : le premier mesure ce
        qui circule à votre sujet, le second ce que vous avez mis en place.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <CourbeDesOuvertes serie={exposure.series} />
        <ExpositionParActif actifs={exposure.by_asset} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Mouvements de la période" subtitle="Ce qui a bougé, et à quel rythme" />
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-600">Nouvelles compromissions détectées</dt>
              <dd className="font-medium text-ink-900">{exposure.new_in_period}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-600">Traitées</dt>
              <dd className="font-medium text-ink-900">{exposure.treated_in_period}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-600">Écartées</dt>
              <dd className="font-medium text-ink-900">{exposure.ignored_in_period}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-600">Délai moyen de traitement</dt>
              <dd className="font-medium text-ink-900">
                {exposure.average_treatment_days === null
                  ? '—'
                  : `${formatNombre(exposure.average_treatment_days)} jours`}
              </dd>
            </div>
          </dl>
        </Card>

        <Card>
          <CardHeader title="Plan d'action" subtitle="Ce qui reste, et ce qui traîne" />
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-600">Actions ouvertes</dt>
              <dd className="font-medium text-ink-900">{plan.open}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-600">Terminées sur la période</dt>
              <dd className="font-medium text-ink-900">{plan.completed_in_period}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-600">En retard</dt>
              <dd className="font-medium text-ink-900">
                {plan.overdue}
                {plan.overdue > 0 && (
                  <Badge variant="critical" className="ml-2">
                    à arbitrer
                  </Badge>
                )}
              </dd>
            </div>
            {/* Sans cette ligne, « 2 actions en retard » sur quarante sans
                échéance se lirait comme une bonne nouvelle. */}
            <div className="flex justify-between">
              <dt className="text-ink-600">Ouvertes sans échéance</dt>
              <dd className="font-medium text-ink-900">{plan.without_due_date}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-600">Taux d’avancement</dt>
              <dd className="font-medium text-ink-900">
                {plan.completion_rate === null ? '—' : `${formatNombre(plan.completion_rate)} %`}
              </dd>
            </div>
          </dl>
        </Card>
      </div>

      {monitoring.certificates?.length > 0 && (
        <Card>
          <CardHeader
            title="Certificats à renouveler"
            subtitle="Un certificat expiré rend le site inaccessible et affiche un avertissement aux visiteurs"
          />
          <ul className="space-y-2 text-sm">
            {monitoring.certificates.map((cert) => (
              <li key={cert.asset_id} className="flex justify-between">
                <span className="truncate text-ink-800">{cert.asset_value}</span>
                <span className="shrink-0 text-ink-600">
                  dans {cert.days_left} jour{cert.days_left > 1 ? 's' : ''}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {currentTenant && (
        <p className="t-meta">
          Chiffres arrêtés au {formatJour(period.end)}. Le rapport PDF et le tableur reprennent
          exactement ces valeurs.
        </p>
      )}
    </div>
  )
}
