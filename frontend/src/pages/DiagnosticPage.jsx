import { CheckCircle2, ChevronLeft, ChevronRight } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { assessmentsApi } from '../api/endpoints'
import { FeatureLockedNotice } from '../components/FeatureGate'
import { useEntitlements } from '../context/EntitlementsContext'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import SegmentedControl from '../components/ui/SegmentedControl'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

const VALUE_OPTIONS = [
  { value: 'yes', label: 'Oui' },
  { value: 'partial', label: 'Partiellement' },
  { value: 'no', label: 'Non' },
  { value: 'na', label: 'Non applicable' },
]

function ProgressBar({ answered, total, className = '' }) {
  const pct = total > 0 ? Math.round((answered / total) * 100) : 0
  return (
    <div className={`h-1.5 overflow-hidden rounded-full bg-ink-100 ${className}`}>
      <div className="transition-smooth h-full rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
    </div>
  )
}

function CompletionCelebration({ assessmentId }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-ink-200 bg-surface px-6 py-16 text-center">
      <div className="flex size-14 items-center justify-center rounded-full bg-ok-subtle text-ok-strong">
        <CheckCircle2 className="size-8" aria-hidden="true" />
      </div>
      <h1 className="mt-5 font-display text-2xl font-semibold text-ink-900">Diagnostic terminé</h1>
      <p className="mt-2 max-w-md text-sm text-ink-500">
        Merci d’avoir répondu à l’ensemble des mesures. Votre score de maturité et votre plan
        d’action sont prêts.
      </p>
      <Link to={`/resultats/${assessmentId}`} className="mt-6">
        <Button variant="primary">Voir mes résultats</Button>
      </Link>
    </div>
  )
}

export default function DiagnosticPage() {
  const { showToast } = useToast()
  const [referential, setReferential] = useState(null)
  const [assessment, setAssessment] = useState(null)
  const [answers, setAnswers] = useState({})
  const [savingMeasureId, setSavingMeasureId] = useState(null)
  const [completing, setCompleting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [justCompleted, setJustCompleted] = useState(false)
  const [currentDomainIndex, setCurrentDomainIndex] = useState(0)
  const initializedIndex = useRef(false)
  const { hasFeature } = useEntitlements()
  const diagnosticInclus = hasFeature('anssi_assessment')

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
      try {
        const referentialRes = await assessmentsApi.referential()
        setReferential(referentialRes.data)
        await loadAssessment()
      } catch (err) {
        // 402 = hors offre. Ce n'est pas une panne, et l'annoncer comme telle
        // ferait croire le produit cassé là où il refuse poliment. L'encart
        // plus bas explique et nomme l'offre qui débloque.
        if (err.response?.status !== 402) {
          showToast({ type: 'error', message: 'Impossible de charger le diagnostic.' })
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [loadAssessment, showToast])

  // Resume where the tenant left off (first domain with an unanswered
  // measure) instead of always restarting the wizard at domain 1.
  useEffect(() => {
    if (initializedIndex.current || !referential || !assessment) return
    initializedIndex.current = true
    const firstIncomplete = assessment.progress.by_domain.findIndex((d) => d.answered < d.total)
    if (firstIncomplete > 0) setCurrentDomainIndex(firstIncomplete)
  }, [referential, assessment])

  async function handleAnswer(measureId, value) {
    setAnswers((prev) => ({ ...prev, [measureId]: value }))
    setSavingMeasureId(measureId)
    try {
      await assessmentsApi.submitAnswer(assessment.id, measureId, value)
      const detail = await assessmentsApi.detail(assessment.id)
      setAssessment(detail.data)
    } catch {
      showToast({ type: 'error', message: 'La réponse n’a pas pu être enregistrée. Réessayez.' })
    } finally {
      setSavingMeasureId(null)
    }
  }

  async function handleComplete() {
    setCompleting(true)
    try {
      await assessmentsApi.complete(assessment.id)
      setJustCompleted(true)
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de terminer l’évaluation.',
        action: { label: 'Réessayer', onClick: handleComplete },
      })
    } finally {
      setCompleting(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }
  // Hors offre AVANT le message d'indisponibilité : sans cet ordre, un client
  // « Veille » lirait « Diagnostic indisponible » — un message de panne pour
  // une limite commerciale. L'encart, lui, décrit la fonctionnalité et nomme
  // l'offre qui la débloque.
  if (!diagnosticInclus) {
    return (
      <div className="space-y-4">
        <h1 className="font-display text-xl font-semibold text-ink-900">
          Diagnostic de maturité
        </h1>
        <FeatureLockedNotice feature="anssi_assessment" />
        <p className="text-sm text-ink-500">
          Les diagnostics que vous avez déjà réalisés restent consultables depuis vos
          résultats.
        </p>
      </div>
    )
  }
  if (!referential || !assessment) {
    return <p className="text-critical-strong">Diagnostic indisponible.</p>
  }
  if (justCompleted) {
    return <CompletionCelebration assessmentId={assessment.id} />
  }

  const { progress } = assessment
  const domain = referential.domains[currentDomainIndex]
  const domainProgress = progress.by_domain.find((d) => d.domain_code === domain.code)
  const isDomainComplete = domainProgress && domainProgress.answered === domainProgress.total
  const isLastDomain = currentDomainIndex === referential.domains.length - 1

  return (
    <div className="space-y-6 pb-24">
      <div className="sticky top-14 z-10 -mx-4 border-b border-ink-200 bg-canvas/95 px-4 py-4 backdrop-blur-sm sm:-mx-6 sm:px-6 lg:-mx-10 lg:px-10">
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <h1 className="font-display text-xl font-semibold text-ink-900">
              Diagnostic de maturité
            </h1>
            <p className="mt-0.5 text-sm text-ink-500">
              Domaine {currentDomainIndex + 1} / {referential.domains.length} — {domain.name}
            </p>
          </div>
          <span className="shrink-0 text-sm font-medium text-ink-500">
            {progress.answered}/{progress.total}
          </span>
        </div>
        <ProgressBar answered={progress.answered} total={progress.total} className="mt-3" />
      </div>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold text-ink-900">{domain.name}</h2>
          {domainProgress && (
            <span className="text-sm text-ink-500">
              {domainProgress.answered}/{domainProgress.total}
            </span>
          )}
        </div>
        {domain.description && <p className="text-sm text-ink-500">{domain.description}</p>}

        <ul className="mt-4 divide-y divide-ink-100">
          {domain.measures.map((measure) => (
            <li key={measure.id} className="py-4 first:pt-0 last:pb-0">
              <p className="text-sm font-medium text-ink-800">{measure.plain_language}</p>
              <p className="mt-0.5 text-xs text-ink-500">{measure.official_title}</p>
              <SegmentedControl
                className="mt-3"
                disabled={savingMeasureId === measure.id}
                value={answers[measure.id]}
                onChange={(value) => handleAnswer(measure.id, value)}
                options={VALUE_OPTIONS}
              />
            </li>
          ))}
        </ul>
      </Card>

      <div className="fixed inset-x-0 bottom-0 z-10 border-t border-ink-200 bg-surface px-4 py-3 sm:px-6 md:pl-20 lg:pl-64 lg:px-10">
        <div className="flex items-center justify-between gap-4">
          <Button
            variant="secondary"
            icon={ChevronLeft}
            disabled={currentDomainIndex === 0}
            onClick={() => setCurrentDomainIndex((i) => Math.max(0, i - 1))}
          >
            Précédent
          </Button>
          {isLastDomain ? (
            <Button
              variant="primary"
              loading={completing}
              disabled={!isDomainComplete}
              onClick={handleComplete}
            >
              Terminer l’évaluation
            </Button>
          ) : (
            <Button
              variant="primary"
              disabled={!isDomainComplete}
              onClick={() => setCurrentDomainIndex((i) => i + 1)}
            >
              Suivant
              <ChevronRight className="size-4" aria-hidden="true" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
