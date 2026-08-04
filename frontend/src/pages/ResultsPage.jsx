import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
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

const RADAR_COLOR = '#4f46e5'

function formatScore(score) {
  return score === null || score === undefined ? 'Non évalué' : `${score}/100`
}

function ScoreTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
      <p className="font-medium text-slate-800">{row.domain}</p>
      <p className="text-slate-500">{formatScore(row.displayScore)}</p>
    </div>
  )
}

export default function ResultsPage() {
  const { assessmentId } = useParams()
  const [assessment, setAssessment] = useState(null)
  const [scores, setScores] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
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
        setError('Impossible de charger les résultats.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [assessmentId])

  if (loading) {
    return <p className="text-slate-500">Chargement des résultats…</p>
  }
  if (error) {
    return <p className="text-red-600">{error}</p>
  }
  if (!assessment || !scores) {
    return (
      <p className="text-slate-600">
        Aucune évaluation terminée pour l’instant. Complétez le diagnostic pour voir vos résultats.
      </p>
    )
  }

  const radarData = scores.by_domain.map((d) => ({
    domain: d.domain_name,
    score: d.score ?? 0,
    displayScore: d.score,
  }))

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Résultats</h1>
        <p className="mt-1 text-sm text-slate-500">
          Évaluation terminée le{' '}
          {new Date(assessment.completed_at).toLocaleDateString('fr-FR', {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
          })}
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-sm font-medium text-slate-500">Score global de maturité</p>
        <p className="mt-1 text-4xl font-semibold text-slate-900">
          {formatScore(scores.global_score)}
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-medium text-slate-500">Score par domaine</h2>
          <div className="mt-2" style={{ height: 360 }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} outerRadius="70%">
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis dataKey="domain" tick={{ fill: '#475569', fontSize: 11 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Radar
                  name="Score"
                  dataKey="score"
                  stroke={RADAR_COLOR}
                  fill={RADAR_COLOR}
                  fillOpacity={0.25}
                />
                <Tooltip content={<ScoreTooltip />} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-medium text-slate-500">Détail par domaine</h2>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="py-2 font-medium">Domaine</th>
                <th className="py-2 text-right font-medium">Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {scores.by_domain.map((d) => (
                <tr key={d.domain_code}>
                  <td className="py-2 text-slate-700">{d.domain_name}</td>
                  <td className="py-2 text-right text-slate-700">{formatScore(d.score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {history.length > 1 && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-medium text-slate-500">Historique des évaluations</h2>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="py-2 font-medium">Date</th>
                <th className="py-2 text-right font-medium">Score global</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {history.map((item) => (
                <tr key={item.id}>
                  <td className="py-2 text-slate-700">
                    {new Date(item.completed_at).toLocaleDateString('fr-FR')}
                  </td>
                  <td className="py-2 text-right text-slate-700">
                    {formatScore(item.score_global)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
