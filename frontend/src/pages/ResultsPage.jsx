import { ArrowRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { assessmentsApi } from '../api/endpoints'
import Button from '../components/ui/Button'
import ScoreGauge from '../components/ui/ScoreGauge'
import Card, { CardHeader } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

const RADAR_COLOR = '#2a4f84' // brand-600

function formatScore(score) {
  return score === null || score === undefined ? 'Non évalué' : `${score}/100`
}

function ScoreTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div className="rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm shadow-elevated">
      <p className="font-medium text-ink-800">{row.domain}</p>
      <p className="text-ink-500">{formatScore(row.displayScore)}</p>
    </div>
  )
}

function domainBarColor(score) {
  if (score === null || score === undefined) return 'bg-ink-300'
  if (score >= 70) return 'bg-ok-strong'
  if (score >= 40) return 'bg-warning-strong'
  return 'bg-critical-strong'
}

export default function ResultsPage() {
  const { assessmentId } = useParams()
  const { showToast } = useToast()
  const [assessment, setAssessment] = useState(null)
  const [scores, setScores] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    async function load() {
      setLoading(true)
      setNotFound(false)
      try {
        const historyRes = await assessmentsApi.list()
        const completedHistory = historyRes.data.results.filter((a) => a.status === 'completed')
        setHistory(completedHistory)

        const targetId = assessmentId || completedHistory[0]?.id
        if (!targetId) {
          setAssessment(null)
          return
        }
        const [assessmentRes, scoresRes] = await Promise.all([
          assessmentsApi.detail(targetId),
          assessmentsApi.scores(targetId),
        ])
        setAssessment(assessmentRes.data)
        setScores(scoresRes.data)
      } catch {
        setNotFound(true)
        showToast({ type: 'error', message: 'Impossible de charger les résultats.' })
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [assessmentId, showToast])

  if (loading) {
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }
  if (notFound) {
    return <p className="text-critical-strong">Impossible de charger les résultats.</p>
  }
  if (!assessment || !scores) {
    return (
      // Le titre de page reste, même sans données. C'est ce qu'un lecteur
      // d'écran annonce en arrivant : sans lui, la page se présente sans nom,
      // et l'état vide devient le seul repère — alors qu'il décrit une
      // situation, pas la page. Le défaut était rapporté par axe
      // (`page-has-heading-one`) mais classé « moderate », donc écarté par
      // notre propre seuil de balayage jusqu'à ce qu'il soit abaissé.
      <div className="space-y-6">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-900">Résultats</h1>
          <p className="mt-1 text-sm text-ink-500">
            Votre score de maturité et son détail par domaine.
          </p>
        </div>
        <EmptyState
          title="Aucune évaluation terminée"
          description="Complétez le diagnostic pour voir vos résultats et votre score de maturité."
          action={
            <Link to="/diagnostic">
              {/* Bleu de marque, plus ambre : l'ambre ne porte plus d'action
                  depuis la refonte des fondations. Ce bouton avait échappé au
                  balayage parce qu'il n'utilisait pas le composant `Button`. */}
              <Button variant="primary">Démarrer le diagnostic</Button>
            </Link>
          }
        />
      </div>
    )
  }

  const radarData = scores.by_domain.map((d) => ({
    domain: d.domain_name,
    score: d.score ?? 0,
    displayScore: d.score,
  }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Résultats</h1>
        <p className="mt-1 text-sm text-ink-500">
          Évaluation terminée le{' '}
          {new Date(assessment.completed_at).toLocaleDateString('fr-FR', {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
          })}
        </p>
      </div>

      <Card className="flex items-center gap-6">
        <ScoreGauge score={scores.global_score} scale="maturity" size="lg" showLegend />
        <div>
          <p className="text-sm font-medium text-ink-500">Score global de maturité</p>
          <p className="mt-1 font-display text-lg text-ink-700">
            Calculé sur les {scores.by_domain.length} domaines du référentiel ANSSI.
          </p>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Score par domaine" />
          <div style={{ height: 380 }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} outerRadius="65%" margin={{ top: 20, right: 24, bottom: 20, left: 24 }}>
                <PolarGrid stroke="var(--color-ink-200)" />
                <PolarAngleAxis
                  dataKey="domain"
                  tick={{ fill: 'var(--color-ink-600)', fontSize: 11 }}
                  tickFormatter={(name) => (name.length > 16 ? `${name.slice(0, 15)}…` : name)}
                />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: 'var(--color-ink-400)', fontSize: 10 }} />
                <Radar name="Score" dataKey="score" stroke={RADAR_COLOR} fill={RADAR_COLOR} fillOpacity={0.25} />
                <Tooltip content={<ScoreTooltip />} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card padding="p-0">
          <div className="p-6 pb-0">
            <CardHeader title="Détail par domaine" />
          </div>
          <ul className="divide-y divide-ink-100">
            {scores.by_domain.map((d) => (
              <li key={d.domain_code} className="flex items-center gap-4 px-6 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink-700">{d.domain_name}</p>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-100">
                    <div
                      className={`h-full rounded-full ${domainBarColor(d.score)}`}
                      style={{ width: `${d.score ?? 0}%` }}
                    />
                  </div>
                </div>
                <span className="w-16 shrink-0 text-right text-sm text-ink-600">
                  {formatScore(d.score)}
                </span>
                <Link
                  to={`/plan-action?domaine=${encodeURIComponent(d.domain_name)}`}
                  className="transition-smooth shrink-0 text-ink-400 hover:text-brand-600"
                  aria-label={`Voir les mesures en écart pour ${d.domain_name}`}
                >
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {history.length > 1 && (
        <Card padding="p-0">
          <div className="p-6 pb-0">
            <CardHeader title="Historique des évaluations" />
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ink-200 text-left text-ink-500">
                <th className="px-6 py-2 font-medium">Date</th>
                <th className="px-6 py-2 text-right font-medium">Score global</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {history.map((item) => (
                <tr key={item.id}>
                  <td className="px-6 py-2.5 text-ink-700">
                    {new Date(item.completed_at).toLocaleDateString('fr-FR')}
                  </td>
                  <td className="px-6 py-2.5 text-right text-ink-700">
                    {formatScore(item.score_global)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
