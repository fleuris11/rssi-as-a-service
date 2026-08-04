import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { assessmentsApi } from '../api/endpoints'

const VALUE_OPTIONS = [
  { value: 'yes', label: 'Oui' },
  { value: 'partial', label: 'Partiellement' },
  { value: 'no', label: 'Non' },
  { value: 'na', label: 'Non applicable' },
]

function ProgressBar({ answered, total }) {
  const pct = total > 0 ? Math.round((answered / total) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
        <div className="h-full rounded-full bg-slate-900" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 shrink-0 text-right text-sm text-slate-500">
        {answered}/{total}
      </span>
    </div>
  )
}

export default function DiagnosticPage() {
  const navigate = useNavigate()
  const [referential, setReferential] = useState(null)
  const [assessment, setAssessment] = useState(null)
  const [answers, setAnswers] = useState({})
  const [savingMeasureId, setSavingMeasureId] = useState(null)
  const [completing, setCompleting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadAssessment = useCallback(async () => {
    let response
    try {
      response = await assessmentsApi.current()
    } catch (err) {
      if (err.response?.status === 404) {
        response = await assessmentsApi.start()
      } else {
        throw err
      }
    }
    setAssessment(response.data)
    const answerMap = {}
    for (const answer of response.data.answers) {
      answerMap[answer.measure] = answer.value
    }
    setAnswers(answerMap)
  }, [])

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
      try {
        const referentialRes = await assessmentsApi.referential()
        setReferential(referentialRes.data)
        await loadAssessment()
      } catch {
        setError("Impossible de charger le diagnostic. Réessayez dans un instant.")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [loadAssessment])

  async function handleAnswer(measureId, value) {
    setAnswers((prev) => ({ ...prev, [measureId]: value }))
    setSavingMeasureId(measureId)
    setError('')
    try {
      await assessmentsApi.submitAnswer(assessment.id, measureId, value)
      const detail = await assessmentsApi.detail(assessment.id)
      setAssessment(detail.data)
    } catch {
      setError("La réponse n'a pas pu être enregistrée. Réessayez.")
    } finally {
      setSavingMeasureId(null)
    }
  }

  async function handleComplete() {
    setCompleting(true)
    setError('')
    try {
      await assessmentsApi.complete(assessment.id)
      navigate(`/resultats/${assessment.id}`)
    } catch (err) {
      setError(err.response?.data?.detail || "Impossible de terminer l'évaluation.")
    } finally {
      setCompleting(false)
    }
  }

  if (loading) {
    return <p className="text-slate-500">Chargement du diagnostic…</p>
  }
  if (!referential || !assessment) {
    return <p className="text-red-600">{error || 'Diagnostic indisponible.'}</p>
  }

  const { progress } = assessment
  const isComplete = progress.answered === progress.total && progress.total > 0

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Diagnostic de maturité</h1>
        <p className="mt-1 text-sm text-slate-500">
          {referential.name} — répondez à chaque mesure ; votre progression est enregistrée
          automatiquement.
        </p>
        <div className="mt-4">
          <ProgressBar answered={progress.answered} total={progress.total} />
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {referential.domains.map((domain) => {
        const domainProgress = progress.by_domain.find((d) => d.domain_code === domain.code)
        return (
          <section
            key={domain.id}
            className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
          >
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="text-lg font-semibold text-slate-900">{domain.name}</h2>
              {domainProgress && (
                <span className="text-sm text-slate-500">
                  {domainProgress.answered}/{domainProgress.total}
                </span>
              )}
            </div>
            {domain.description && (
              <p className="mt-1 text-sm text-slate-500">{domain.description}</p>
            )}

            <ul className="mt-4 divide-y divide-slate-100">
              {domain.measures.map((measure) => (
                <li key={measure.id} className="py-4 first:pt-0 last:pb-0">
                  <p className="text-sm font-medium text-slate-800">{measure.plain_language}</p>
                  <p className="mt-0.5 text-xs text-slate-400">{measure.official_title}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {VALUE_OPTIONS.map((option) => {
                      const selected = answers[measure.id] === option.value
                      return (
                        <button
                          key={option.value}
                          type="button"
                          disabled={savingMeasureId === measure.id}
                          onClick={() => handleAnswer(measure.id, option.value)}
                          className={`rounded-md border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50 ${
                            selected
                              ? 'border-slate-900 bg-slate-900 text-white'
                              : 'border-slate-300 text-slate-600 hover:border-slate-400'
                          }`}
                        >
                          {option.label}
                        </button>
                      )
                    })}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )
      })}

      <div className="flex justify-end">
        <button
          type="button"
          disabled={!isComplete || completing}
          onClick={handleComplete}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {completing ? 'Finalisation…' : "Terminer l'évaluation"}
        </button>
      </div>
    </div>
  )
}
