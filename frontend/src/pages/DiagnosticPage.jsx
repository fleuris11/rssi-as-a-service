import { CheckCircle2, ChevronLeft, ChevronRight, Lock, Send } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { accessRequestsApi, assessmentsApi } from '../api/endpoints'
import { FeatureLockedNotice } from '../components/FeatureGate'
import { useEntitlements } from '../context/EntitlementsContext'
import Button from '../components/ui/Button'
import Card, { CardHeader } from '../components/ui/Card'
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

/**
 * Les référentiels qui ne sont PAS attribués, affichés en désactivé plutôt que
 * masqués — même parti pris que les fonctionnalités hors offre : le client
 * doit savoir que le produit sait le faire avant de le demander.
 */
function ReferentielsADemander({ referentiels, demandes, onDemander, enCours }) {
  const [ouvert, setOuvert] = useState(null)
  const [motif, setMotif] = useState('')
  if (referentiels.length === 0) return null

  const enAttente = new Set(
    demandes.filter((d) => d.status === 'pending').map((d) => d.subject_key)
  )

  return (
    <Card>
      <CardHeader
        title="Autres référentiels"
        description="Ceux-ci ne vous sont pas attribués. Vous pouvez en faire la demande."
      />
      <ul className="mt-2 divide-y divide-ink-100">
        {referentiels.map((ref) => (
          <li key={ref.slug} className="py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-sm font-medium text-ink-700">
                  <Lock className="size-3.5 shrink-0 text-ink-400" aria-hidden="true" />
                  {ref.name}
                </p>
                <p className="mt-0.5 text-xs text-ink-500">
                  {ref.publisher ? `${ref.publisher} — ` : ''}
                  {ref.measure_count > 0
                    ? `${ref.measure_count} mesures`
                    : 'structure prête, contenu à importer'}
                </p>
              </div>
              {enAttente.has(ref.slug) ? (
                <span className="text-xs text-ink-500">Demande en cours d’examen</span>
              ) : (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setOuvert(ouvert === ref.slug ? null : ref.slug)
                    setMotif('')
                  }}
                >
                  Demander l’accès
                </Button>
              )}
            </div>
            {ouvert === ref.slug && (
              <div className="mt-3 rounded-md border border-ink-200 bg-canvas p-3">
                <label className="text-xs font-medium text-ink-600" htmlFor={`motif-${ref.slug}`}>
                  Pourquoi en avez-vous besoin ? (facultatif)
                </label>
                <textarea
                  id={`motif-${ref.slug}`}
                  className="mt-1.5 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
                  rows={2}
                  value={motif}
                  onChange={(event) => setMotif(event.target.value)}
                  placeholder="Exemple : notre donneur d’ordre l’exige dans son cahier des charges."
                />
                <div className="mt-2 flex justify-end gap-2">
                  <Button variant="ghost" onClick={() => setOuvert(null)}>
                    Annuler
                  </Button>
                  <Button
                    variant="primary"
                    icon={Send}
                    loading={enCours === ref.slug}
                    onClick={async () => {
                      await onDemander(ref, motif)
                      setOuvert(null)
                    }}
                  >
                    Envoyer la demande
                  </Button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function DiagnosticPage() {
  const { showToast } = useToast()
  const [referentiels, setReferentiels] = useState([])
  const [choisi, setChoisi] = useState(null)
  const [demandes, setDemandes] = useState([])
  const [demandeEnCours, setDemandeEnCours] = useState(null)
  const [referential, setReferential] = useState(null)
  const [assessment, setAssessment] = useState(null)
  const [answers, setAnswers] = useState({})
  const [savingMeasureId, setSavingMeasureId] = useState(null)
  const [completing, setCompleting] = useState(false)
  const [starting, setStarting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [justCompleted, setJustCompleted] = useState(false)
  const [currentDomainIndex, setCurrentDomainIndex] = useState(0)
  const initializedIndex = useRef(false)
  // `showToast` par référence, et non en dépendance d'effet : le fournisseur
  // en rend une nouvelle fonction à chaque rendu, et un effet qui en dépend
  // se relance en boucle — l'écran reste alors sur son squelette de
  // chargement. Le défaut est invisible tant qu'on ne regarde que la page
  // finie ; il se voit au premier test.
  const toastRef = useRef(showToast)
  toastRef.current = showToast
  const { hasFeature } = useEntitlements()
  const diagnosticInclus = hasFeature('anssi_assessment')

  const attribues = referentiels.filter((r) => r.granted)
  const aDemander = referentiels.filter((r) => !r.granted && !r.readable)

  const chargerEvaluation = useCallback(async (slug, { demarrer = false } = {}) => {
    try {
      const response = await assessmentsApi.current(slug)
      return response.data
    } catch (err) {
      if (err.response?.status !== 404) throw err
      // Pas de diagnostic en cours. On n'en crée un tout seul que lorsqu'il
      // n'y a rien à choisir : avec plusieurs référentiels, se promener d'un
      // onglet à l'autre ouvrirait autant d'évaluations vides.
      if (!demarrer) return null
      const created = await assessmentsApi.start(slug)
      return created.data
    }
  }, [])

  const appliquerEvaluation = useCallback((donnees) => {
    setAssessment(donnees)
    const parMesure = {}
    for (const answer of donnees?.answers ?? []) parMesure[answer.measure] = answer.value
    setAnswers(parMesure)
  }, [])

  // 1. Le catalogue : ce que cette entreprise peut évaluer, et ce qu'elle
  //    pourrait demander.
  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const [catalogue, mesDemandes] = await Promise.all([
          assessmentsApi.listReferentials(),
          accessRequestsApi.list().catch(() => ({ data: [] })),
        ])
        setReferentiels(catalogue.data)
        setDemandes(mesDemandes.data)
        setChoisi(catalogue.data.find((r) => r.granted)?.slug ?? null)
      } catch (err) {
        if (err.response?.status !== 402) {
          toastRef.current({ type: 'error', message: 'Impossible de charger le diagnostic.' })
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // 2. Le questionnaire du référentiel choisi.
  useEffect(() => {
    if (!choisi) return
    let annule = false
    async function load() {
      setLoading(true)
      initializedIndex.current = false
      setCurrentDomainIndex(0)
      try {
        const structure = await assessmentsApi.referential(choisi)
        // Démarrage automatique conservé quand il n'y a qu'un référentiel :
        // c'est le parcours d'avant V2-4, et il n'y a rien à choisir.
        const evaluation = await chargerEvaluation(choisi, {
          demarrer: attribues.length <= 1,
        })
        if (annule) return
        setReferential(structure.data)
        appliquerEvaluation(evaluation)
      } catch (err) {
        if (!annule && err.response?.status !== 402) {
          toastRef.current({ type: 'error', message: 'Impossible de charger le référentiel.' })
        }
      } finally {
        if (!annule) setLoading(false)
      }
    }
    load()
    return () => {
      annule = true
    }
    // `attribues.length` et non `attribues` : la liste est reconstruite à
    // chaque rendu, la mettre en dépendance relancerait le chargement en
    // boucle.
  }, [choisi, attribues.length, chargerEvaluation, appliquerEvaluation])

  useEffect(() => {
    if (initializedIndex.current || !referential || !assessment) return
    initializedIndex.current = true
    const firstIncomplete = assessment.progress.by_domain.findIndex((d) => d.answered < d.total)
    if (firstIncomplete > 0) setCurrentDomainIndex(firstIncomplete)
  }, [referential, assessment])

  async function handleDemander(ref, motif) {
    setDemandeEnCours(ref.slug)
    try {
      const response = await accessRequestsApi.create({
        subject_type: 'referential',
        subject_key: ref.slug,
        reason: motif,
      })
      setDemandes((prev) => [response.data, ...prev])
      showToast({
        type: 'success',
        message: 'Demande envoyée. Nous revenons vers vous rapidement.',
      })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'La demande n’a pas pu être envoyée.',
      })
    } finally {
      setDemandeEnCours(null)
    }
  }

  async function handleStart() {
    setStarting(true)
    try {
      const response = await assessmentsApi.start(choisi)
      appliquerEvaluation(response.data)
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de démarrer le diagnostic.',
      })
    } finally {
      setStarting(false)
    }
  }

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

  const selecteur =
    attribues.length > 1 ? (
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Référentiels">
        {attribues.map((ref) => (
          <button
            key={ref.slug}
            type="button"
            role="tab"
            aria-selected={ref.slug === choisi}
            onClick={() => setChoisi(ref.slug)}
            className={`transition-smooth rounded-full border px-3 py-1.5 text-sm ${
              ref.slug === choisi
                ? 'border-brand-600 bg-brand-600 text-white'
                : 'border-ink-200 bg-surface text-ink-600 hover:border-brand-600'
            }`}
          >
            {ref.name}
          </button>
        ))}
      </div>
    ) : null

  // Aucun référentiel attribué : ce n'est pas une panne, c'est une situation
  // qui se règle par une demande.
  if (attribues.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink-900">
            Diagnostic de maturité
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Aucun référentiel ne vous est attribué pour le moment.
          </p>
        </div>
        <ReferentielsADemander
          referentiels={aDemander}
          demandes={demandes}
          onDemander={handleDemander}
          enCours={demandeEnCours}
        />
      </div>
    )
  }

  if (justCompleted) {
    return <CompletionCelebration assessmentId={assessment.id} />
  }

  if (!referential) {
    return <p className="text-critical-strong">Diagnostic indisponible.</p>
  }

  // Référentiel choisi, aucun diagnostic ouvert dessus : on demande le geste
  // plutôt que d'ouvrir une évaluation que personne n'a demandée.
  if (!assessment) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink-900">
            Diagnostic de maturité
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Choisissez le référentiel sur lequel vous souhaitez vous évaluer.
          </p>
        </div>
        {selecteur}
        <Card>
          <CardHeader
            title={referential.name}
            description={referential.description || referential.publisher}
          />
          <p className="mt-2 text-sm text-ink-500">
            {referential.domains.reduce((total, d) => total + d.measures.length, 0)} mesures,{' '}
            {referential.domains.length} domaines.
          </p>
          {referential.licence_notice && (
            <p className="mt-2 text-xs text-ink-400">{referential.licence_notice}</p>
          )}
          <div className="mt-4">
            <Button variant="primary" loading={starting} onClick={handleStart}>
              Démarrer ce diagnostic
            </Button>
          </div>
        </Card>
        <ReferentielsADemander
          referentiels={aDemander}
          demandes={demandes}
          onDemander={handleDemander}
          enCours={demandeEnCours}
        />
      </div>
    )
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
              {referential.name}
              {assessment.subset_name ? ` — ${assessment.subset_name}` : ''} · Domaine{' '}
              {currentDomainIndex + 1} / {referential.domains.length} — {domain.name}
            </p>
          </div>
          <span className="shrink-0 text-sm font-medium text-ink-500">
            {progress.answered}/{progress.total}
          </span>
        </div>
        <ProgressBar answered={progress.answered} total={progress.total} className="mt-3" />
        {selecteur && <div className="mt-3">{selecteur}</div>}
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
              {/* `statement` et non `plain_language` : c'est l'énoncé du
                  client quand il a reformulé la mesure, l'énoncé d'origine
                  sinon. */}
              <p className="text-sm font-medium text-ink-800">{measure.statement}</p>
              <p className="mt-0.5 text-xs text-ink-500">{measure.official_title}</p>
              {measure.context_note && (
                <p className="mt-1 text-xs italic text-ink-500">{measure.context_note}</p>
              )}
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

      {/* Aussi ici, et pas seulement sur l'écran de choix : un client qui n'a
          qu'un référentiel entre directement dans le questionnaire et ne
          verrait jamais qu'il peut en demander un autre. */}
      <ReferentielsADemander
        referentiels={aDemander}
        demandes={demandes}
        onDemander={handleDemander}
        enCours={demandeEnCours}
      />

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
