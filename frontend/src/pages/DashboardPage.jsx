import {
  ArrowRight,
  ClipboardCheck,
  CloudLightning,
  CloudSun,
  KanbanSquare,
  Minus,
  Radar,
  ScrollText,
  ShieldAlert,
  Sun,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { actionsApi, assessmentsApi, monitoringApi, threatIntelligenceApi } from '../api/endpoints'
import FeatureGate from '../components/FeatureGate'
import ScoreGauge from '../components/ui/ScoreGauge'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card, { CardHeader } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

const QUICK_LINKS = [
  { to: '/diagnostic', label: 'Diagnostic', icon: ClipboardCheck },
  { to: '/plan-action', label: "Plan d'action", icon: KanbanSquare },
  { to: '/surveillance', label: 'Surveillance', icon: Radar },
  { to: '/compromissions', label: 'Compromissions', icon: ShieldAlert },
  { to: '/documents', label: 'Documents', icon: ScrollText },
]

function worstStatus(dashboardRows) {
  let worst = 'ok'
  for (const row of dashboardRows) {
    if (row.open_alerts.some((a) => a.severity === 'critical')) return 'critical'
    if (row.open_alerts.length > 0) worst = 'warning'
    for (const check of Object.values(row.latest_checks)) {
      if (check?.status === 'critical') return 'critical'
      if (check?.status === 'warning') worst = 'warning'
    }
  }
  return worst
}

const WEATHER = {
  ok: { icon: Sun, label: 'Tout va bien', color: 'text-ok-strong', variant: 'ok' },
  warning: { icon: CloudSun, label: 'Points de vigilance', color: 'text-warning-strong', variant: 'warning' },
  critical: { icon: CloudLightning, label: 'Attention requise', color: 'text-critical-strong', variant: 'critical' },
}

function OnboardingSteps() {
  const steps = [
    {
      title: 'Faites votre diagnostic',
      description: 'Répondez au questionnaire ANSSI pour connaître votre score de maturité.',
      to: '/diagnostic',
      cta: 'Démarrer le diagnostic',
      icon: ClipboardCheck,
      // Conditionne l'étape à l'offre. Le nom de la clé vient du registre
      // serveur : l'interface n'invente pas de fonctionnalité.
      feature: 'anssi_assessment',
    },
    {
      title: 'Suivez votre plan',
      description: 'Un plan d’action priorisé est généré automatiquement à partir des écarts.',
      to: '/plan-action',
      cta: 'Voir le plan',
      icon: KanbanSquare,
    },
    {
      title: 'Surveillez vos actifs',
      description: 'Déclarez votre site et vos domaines pour recevoir la météo cyber quotidienne.',
      to: '/surveillance',
      cta: 'Ajouter un actif',
      icon: Radar,
    },
  ]

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {steps.map((step, index) => (
        <Card key={step.title} className="flex flex-col">
          <div className="flex items-center gap-2 text-xs font-medium text-brand-600">
            <span className="flex size-5 items-center justify-center rounded-full bg-brand-100 text-[11px]">
              {index + 1}
            </span>
            Étape {index + 1}
          </div>
          <div className="mt-3 flex size-10 items-center justify-center rounded-md bg-brand-50 text-brand-700">
            <step.icon className="size-5" aria-hidden="true" />
          </div>
          <p className="mt-3 font-display text-base font-semibold text-ink-900">{step.title}</p>
          <p className="mt-1 flex-1 text-sm text-ink-500">{step.description}</p>
          {/* L'étape reste VISIBLE et décrite quand elle est hors offre :
              seul son bouton est désactivé, avec le teaser et l'offre requise.
              Retirer la carte ferait disparaître du parcours d'accueil la
              première chose que le produit sait faire. */}
          {step.feature ? (
            <FeatureGate feature={step.feature}>
              <Link to={step.to} className="mt-4 block">
                <Button variant={index === 0 ? 'primary' : 'secondary'} className="w-full">
                  {step.cta}
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Button>
              </Link>
            </FeatureGate>
          ) : (
            <Link to={step.to} className="mt-4">
              <Button variant={index === 0 ? 'primary' : 'secondary'} className="w-full">
                {step.cta}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Button>
            </Link>
          )}
        </Card>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const [loading, setLoading] = useState(true)
  const [assessments, setAssessments] = useState([])
  const [dashboardRows, setDashboardRows] = useState([])
  const [actionItems, setActionItems] = useState([])
  const [breachFindings, setBreachFindings] = useState([])
  const { showToast } = useToast()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [assessmentsRes, dashboardRes, items, findingsRes] = await Promise.all([
        assessmentsApi.list(),
        monitoringApi.dashboard(),
        actionsApi.listAll(),
        threatIntelligenceApi.listFindings('open'),
      ])
      setAssessments(assessmentsRes.data.results.filter((a) => a.status === 'completed'))
      setDashboardRows(dashboardRes.data)
      setActionItems(items)
      setBreachFindings(findingsRes.data.results)
    } catch {
      showToast({
        type: 'error',
        message: 'Impossible de charger le tableau de bord.',
        action: { label: 'Réessayer', onClick: load },
      })
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (loading) {
    return (
      <div className="grid gap-6 lg:grid-cols-3">
        <SkeletonCard className="lg:col-span-2" />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  const hasAnyData = assessments.length > 0

  if (!hasAnyData) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-900">
            Bienvenue sur RSSI as a Service
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Trois étapes pour avoir une vision complète de votre posture cyber.
          </p>
        </div>
        <OnboardingSteps />
      </div>
    )
  }

  const latest = assessments[0]
  const previous = assessments[1]
  const trend =
    previous && latest.score_global !== null && previous.score_global !== null
      ? latest.score_global - previous.score_global
      : null

  const criticalBreachFindings = breachFindings.filter((f) => f.severity === 'critical')
  const weatherKey = criticalBreachFindings.length > 0 ? 'critical' : worstStatus(dashboardRows)
  const weather = WEATHER[weatherKey]
  const openAlerts = dashboardRows.flatMap((row) =>
    row.open_alerts.map((alert) => ({ ...alert, assetValue: row.asset.value }))
  )

  const doneCount = actionItems.filter((i) => i.status === 'done').length
  const totalCount = actionItems.length
  const quickWins = actionItems
    .filter((i) => i.status !== 'done' && i.measure.impact === 'high' && i.measure.effort === 'low')
    .slice(0, 3)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Tableau de bord</h1>
        <p className="mt-1 text-sm text-ink-500">Votre posture cybersécurité en un coup d’œil.</p>
      </div>

      {criticalBreachFindings.length > 0 && (
        <Link
          to="/compromissions"
          className="transition-smooth flex items-center gap-3 rounded-lg border border-critical-strong/20 bg-critical-subtle px-4 py-3 hover:bg-critical-subtle/70"
        >
          <ShieldAlert className="size-5 shrink-0 text-critical-strong" aria-hidden="true" />
          <p className="flex-1 text-sm font-medium text-critical-strong">
            {criticalBreachFindings.length} compromission{criticalBreachFindings.length > 1 ? 's' : ''}{' '}
            critique{criticalBreachFindings.length > 1 ? 's' : ''} détectée
            {criticalBreachFindings.length > 1 ? 's' : ''} — action immédiate recommandée.
          </p>
          <ArrowRight className="size-4 shrink-0 text-critical-strong" aria-hidden="true" />
        </Link>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Hero: compliance score */}
        <Card className="flex items-center gap-6 lg:col-span-2">
          <ScoreGauge score={latest.score_global} scale="maturity" size="md" showLegend />
          <div>
            <p className="text-sm font-medium text-ink-500">Score de conformité</p>
            <p className="mt-1 font-display text-lg font-semibold text-ink-900">
              Évaluation du{' '}
              {new Date(latest.completed_at).toLocaleDateString('fr-FR', {
                day: 'numeric',
                month: 'long',
              })}
            </p>
            {trend !== null && (
              <p
                className={`mt-2 inline-flex items-center gap-1 text-sm font-medium ${
                  trend > 0 ? 'text-ok-strong' : trend < 0 ? 'text-critical-strong' : 'text-ink-500'
                }`}
              >
                {trend > 0 ? (
                  <TrendingUp className="size-4" aria-hidden="true" />
                ) : trend < 0 ? (
                  <TrendingDown className="size-4" aria-hidden="true" />
                ) : (
                  <Minus className="size-4" aria-hidden="true" />
                )}
                {trend > 0 ? '+' : ''}
                {trend} points depuis la dernière évaluation
              </p>
            )}
            <Link to="/resultats" className="mt-3 inline-block">
              <Button variant="secondary" size="sm">
                Voir le détail
                <ArrowRight className="size-3.5" aria-hidden="true" />
              </Button>
            </Link>
          </div>
        </Card>

        {/* Weather */}
        <Card>
          <CardHeader title="Météo du jour" />
          {dashboardRows.length === 0 ? (
            <EmptyState
              icon={Radar}
              title="Aucun actif surveillé"
              description="Déclarez un site ou un domaine pour activer la météo cyber."
              action={
                <Link to="/surveillance">
                  <Button variant="secondary" size="sm">
                    Ajouter un actif
                  </Button>
                </Link>
              }
            />
          ) : (
            <div className="flex items-center gap-4">
              <weather.icon className={`size-10 ${weather.color}`} aria-hidden="true" />
              <div>
                <p className="font-display text-base font-semibold text-ink-900">{weather.label}</p>
                <p className="text-sm text-ink-500">
                  {dashboardRows.length} actif{dashboardRows.length > 1 ? 's' : ''} surveillé
                  {dashboardRows.length > 1 ? 's' : ''}
                </p>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Open alerts */}
        <Card>
          <CardHeader
            title="Alertes ouvertes"
            action={openAlerts.length > 0 && <Badge variant="critical">{openAlerts.length}</Badge>}
          />
          {openAlerts.length === 0 ? (
            <p className="text-sm text-ink-500">Aucune alerte ouverte — tout est sous contrôle.</p>
          ) : (
            <ul className="space-y-2.5">
              {openAlerts.slice(0, 4).map((alert) => (
                <li key={alert.id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="truncate text-ink-700">{alert.assetValue}</span>
                  <Badge variant={alert.severity === 'critical' ? 'critical' : 'warning'}>
                    {alert.severity === 'critical' ? 'Critique' : 'Avertissement'}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
          <Link to="/surveillance" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700">
            Voir la surveillance
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        </Card>

        {/* Action plan progress */}
        <Card>
          <CardHeader title="Plan d'action" />
          {totalCount === 0 ? (
            <p className="text-sm text-ink-500">
              Aucune action pour l’instant — complétez le diagnostic pour générer votre plan.
            </p>
          ) : (
            <>
              <p className="text-sm text-ink-600">
                <span className="font-display text-xl font-semibold text-ink-900">{doneCount}</span>{' '}
                / {totalCount} mesures faites
              </p>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-ink-100">
                <div
                  className="h-full rounded-full bg-ok-strong transition-smooth"
                  style={{ width: `${totalCount ? (doneCount / totalCount) * 100 : 0}%` }}
                />
              </div>
              {quickWins.length > 0 && (
                <div className="mt-4">
                  <p className="mb-2 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-accent-700">
                    <Zap className="size-3.5" aria-hidden="true" />
                    Prochains quick wins
                  </p>
                  <ul className="space-y-1.5">
                    {quickWins.map((item) => (
                      <li key={item.id} className="truncate text-sm text-ink-700">
                        {item.measure.official_title}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
          <Link to="/plan-action" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700">
            Voir le plan complet
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        </Card>

        {/* Quick access */}
        <Card>
          <CardHeader title="Accès rapides" />
          <div className="grid grid-cols-2 gap-2">
            {QUICK_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className="transition-smooth flex flex-col items-center gap-2 rounded-md border border-ink-200 px-3 py-3 text-center text-xs font-medium text-ink-700 hover:border-brand-300 hover:bg-brand-50"
              >
                <link.icon className="size-5 text-brand-600" aria-hidden="true" />
                {link.label}
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
