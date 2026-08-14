import {
  Activity,
  Building2,
  ClipboardList,
  Gauge,
  Inbox,
  Settings,
  Tags,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../api/endpoints'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Card, { CardHeader } from '../../components/ui/Card'
import { SkeletonCard } from '../../components/ui/Skeleton'
import Tabs from '../../components/ui/Tabs'
import { useToast } from '../../components/ui/Toast'

const TABS = [
  { id: 'capacity', label: 'Ressources', icon: Gauge },
  { id: 'tenants', label: 'Clients', icon: Building2 },
  { id: 'demo', label: 'Demandes', icon: Inbox },
  { id: 'plans', label: 'Offres', icon: Tags },
  { id: 'health', label: 'Santé', icon: Activity },
  { id: 'config', label: 'Configuration', icon: Settings },
  { id: 'audit', label: 'Journal', icon: ClipboardList },
]

const STATUS_VARIANT = {
  active: 'ok',
  trial: 'brand',
  suspended: 'warning',
  cancelled: 'neutral',
  expired: 'critical',
}

function ratioVariant(ratio) {
  if (ratio >= 0.95) return 'critical'
  if (ratio >= 0.8) return 'warning'
  return 'ok'
}

/** Jauge d'une ressource rare : ce que l'exploitant doit voir en permanence. */
function ResourceGauge({ resource }) {
  const percent = Math.min(100, Math.round(resource.ratio * 100))
  const variant = ratioVariant(resource.ratio)
  const barColor = {
    ok: 'bg-ok-strong',
    warning: 'bg-warning-strong',
    critical: 'bg-critical-strong',
  }[variant]

  return (
    <div className="rounded-lg border border-ink-200 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-ink-800">{resource.label}</p>
        <Badge variant={variant}>{percent} %</Badge>
      </div>
      <p className="mt-2 font-display text-2xl font-semibold text-ink-900">
        {resource.used}
        <span className="text-base font-normal text-ink-500"> / {resource.capacity}</span>
      </p>
      <div
        className="mt-3 h-2 overflow-hidden rounded-full bg-ink-100"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={resource.label}
      >
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-2 text-xs text-ink-500">
        {resource.remaining} disponible{resource.remaining > 1 ? 's' : ''}
      </p>
    </div>
  )
}

function CapacityPanel({ data }) {
  if (!data) return null
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Ressources rares de la plateforme" />
        <p className="mb-4 text-sm text-ink-600">
          Ces plafonds sont ceux de la licence et s’appliquent à la plateforme entière, pas à
          chaque client. Toute activation qui les dépasserait est refusée avant enregistrement.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {data.resources.map((resource) => (
            <ResourceGauge key={resource.resource} resource={resource} />
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Projection par offre" />
        <p className="mb-4 text-sm text-ink-600">
          Ce qu’il resterait d’emplacements de surveillance si vous activiez un client
          supplémentaire sur chaque offre.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
                <th className="py-2 pr-4 font-medium">Offre</th>
                <th className="py-2 pr-4 font-medium">Emplacements</th>
                <th className="py-2 pr-4 font-medium">Engagerait</th>
                <th className="py-2 pr-4 font-medium">Resterait</th>
                <th className="py-2 font-medium">Possible</th>
              </tr>
            </thead>
            <tbody>
              {data.projections.map((row) => (
                <tr key={row.plan_code} className="border-b border-ink-100 last:border-0">
                  <td className="py-2 pr-4 text-ink-800">{row.plan_name}</td>
                  <td className="py-2 pr-4 text-ink-600">+{row.monitored_assets}</td>
                  <td className="py-2 pr-4 text-ink-600">
                    {row.would_use} / {row.capacity}
                  </td>
                  <td className="py-2 pr-4 text-ink-600">{row.remaining_after}</td>
                  <td className="py-2">
                    <Badge variant={row.would_fit ? 'ok' : 'critical'}>
                      {row.would_fit ? 'Oui' : 'Non — plafond atteint'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <CardHeader title="Répartition par client" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
                <th className="py-2 pr-4 font-medium">Client</th>
                <th className="py-2 pr-4 font-medium">Offre</th>
                <th className="py-2 pr-4 font-medium">État</th>
                <th className="py-2 pr-4 font-medium">Emplacements</th>
                <th className="py-2 font-medium">Analyses ce mois</th>
              </tr>
            </thead>
            <tbody>
              {data.by_tenant.map((row) => (
                <tr key={row.tenant_id} className="border-b border-ink-100 last:border-0">
                  <td className="py-2 pr-4 text-ink-800">{row.tenant_name}</td>
                  <td className="py-2 pr-4 text-ink-600">{row.plan_name}</td>
                  <td className="py-2 pr-4">
                    <Badge variant={STATUS_VARIANT[row.status] || 'neutral'}>{row.status}</Badge>
                  </td>
                  <td className="py-2 pr-4 text-ink-600">{row.monitored_assets}</td>
                  <td className="py-2 text-ink-600">{row.monthly_scans_used}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function TenantsPanel({ tenants, onAction, busyId }) {
  return (
    <Card>
      <CardHeader title="Clients" />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
              <th className="py-2 pr-4 font-medium">Entreprise</th>
              <th className="py-2 pr-4 font-medium">Offre</th>
              <th className="py-2 pr-4 font-medium">État</th>
              <th className="py-2 pr-4 font-medium">Utilisateurs</th>
              <th className="py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((tenant) => (
              <tr key={tenant.id} className="border-b border-ink-100 last:border-0">
                <td className="py-2.5 pr-4 text-ink-800">{tenant.name}</td>
                <td className="py-2.5 pr-4 text-ink-600">{tenant.plan_name || '—'}</td>
                <td className="py-2.5 pr-4">
                  <Badge variant={STATUS_VARIANT[tenant.subscription_status] || 'neutral'}>
                    {tenant.subscription_status_label}
                  </Badge>
                </td>
                <td className="py-2.5 pr-4 text-ink-600">{tenant.user_count ?? 0}</td>
                <td className="py-2.5">
                  <span className="flex flex-wrap gap-2">
                    {tenant.subscription_status !== 'active' && (
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={busyId === tenant.id}
                        onClick={() => onAction(tenant.id, 'activate')}
                      >
                        Activer
                      </Button>
                    )}
                    {tenant.subscription_status !== 'suspended' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={busyId === tenant.id}
                        onClick={() => onAction(tenant.id, 'suspend')}
                      >
                        Suspendre
                      </Button>
                    )}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

const DEMO_STATUS_VARIANT = {
  new: 'brand',
  contacted: 'neutral',
  scheduled: 'ok',
  closed: 'neutral',
}

function DemoRequestsPanel({ demoRequests, onConvert, onSetStatus, busyId }) {
  if (!demoRequests) return null
  const requests = demoRequests.requests || []

  return (
    <Card>
      <CardHeader title="Demandes de démonstration" />
      <p className="mb-4 text-sm text-ink-600">
        Reçues depuis le site public. Convertir une demande crée l’entreprise, son
        utilisateur administrateur et son essai — l’opération est refusée si elle
        dépasserait les plafonds de la plateforme.
      </p>

      {requests.length === 0 && <p className="text-sm text-ink-500">Aucune demande reçue.</p>}

      <ul className="space-y-3">
        {requests.map((demoRequest) => (
          <li
            key={demoRequest.id}
            className="rounded-lg border border-ink-200 px-4 py-3"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-medium text-ink-900">{demoRequest.company}</p>
              <Badge variant={DEMO_STATUS_VARIANT[demoRequest.status] || 'neutral'}>
                {demoRequest.status_label}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-ink-600">
              {demoRequest.full_name}
              {demoRequest.role ? ` — ${demoRequest.role}` : ''} · {demoRequest.email}
              {demoRequest.company_size_label ? ` · ${demoRequest.company_size_label}` : ''}
            </p>
            {demoRequest.message && (
              <p className="mt-2 whitespace-pre-line text-sm text-ink-600">
                {demoRequest.message}
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {demoRequest.status !== 'contacted' && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busyId === demoRequest.id}
                  onClick={() => onSetStatus(demoRequest.id, 'contacted')}
                >
                  Marquer contactée
                </Button>
              )}
              {demoRequest.already_client ? (
                // Le bouton disparaît plutôt que d'échouer en 409 : le tenant
                // existe déjà, il se pilote depuis l'onglet Clients.
                <span className="self-center text-sm text-ink-500">Déjà cliente</span>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busyId === demoRequest.id}
                  onClick={() => onConvert(demoRequest.id)}
                >
                  Convertir en client
                </Button>
              )}
              {demoRequest.status !== 'closed' && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busyId === demoRequest.id}
                  onClick={() => onSetStatus(demoRequest.id, 'closed')}
                >
                  Clore
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function PlansPanel({ plans, onToggleStatus, busyCode }) {
  return (
    <Card>
      <CardHeader title="Offres" />
      <p className="mb-4 text-sm text-ink-600">
        Publier ou retirer une offre est immédiat et ne demande aucun redéploiement. Une offre
        retirée disparaît du site public mais reste attachée à ses abonnés.
      </p>
      <div className="space-y-3">
        {plans.map((plan) => (
          <div
            key={plan.code}
            className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-ink-200 p-4"
          >
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium text-ink-900">{plan.name}</p>
                <Badge variant={plan.status === 'published' ? 'ok' : 'neutral'}>
                  {plan.status_label}
                </Badge>
                {plan.is_highlighted && <Badge variant="brand">Mise en avant</Badge>}
              </div>
              <p className="mt-1 text-xs text-ink-500">
                {plan.is_quote_only
                  ? 'Sur devis'
                  : `${plan.price_monthly} ${plan.currency} / mois`}{' '}
                — {plan.monitored_assets} actif(s), {plan.monthly_scans} analyses,{' '}
                {plan.max_users === 0 ? 'utilisateurs illimités' : `${plan.max_users} utilisateurs`}
              </p>
              <p className="mt-1 text-xs text-ink-500">
                {plan.feature_labels.join(' · ') || 'Aucune fonctionnalité optionnelle'}
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={busyCode === plan.code}
              onClick={() =>
                onToggleStatus(plan.code, plan.status === 'published' ? 'retired' : 'published')
              }
            >
              {plan.status === 'published' ? 'Retirer' : 'Publier'}
            </Button>
          </div>
        ))}
      </div>
    </Card>
  )
}

// Le serveur renvoie des clés techniques ; l'exploitant lit des libellés.
// Une clé inconnue (nouveau compteur côté serveur) est affichée telle quelle
// plutôt que masquée : mieux vaut un libellé brut qu'un chiffre disparu.
const VOLUME_LABELS = {
  tenants_total: 'Clients enregistrés',
  tenants_active: 'Clients actifs',
  findings_total: 'Expositions détectées',
  reveals_total: 'Consultations de secret',
  demo_requests_new: 'Demandes de démonstration à traiter',
}

function HealthPanel({ health }) {
  if (!health) return null
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="État des services" />
        <ul className="space-y-2">
          {health.checks.map((check) => (
            <li
              key={check.name}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-ink-50 px-3 py-2"
            >
              <span className="text-sm text-ink-800">{check.label}</span>
              <span className="flex items-center gap-3">
                {check.detail && <span className="text-xs text-ink-500">{check.detail}</span>}
                <Badge variant={check.healthy ? 'ok' : 'critical'} dot>
                  {check.healthy ? 'Opérationnel' : 'En échec'}
                </Badge>
              </span>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardHeader title="Tâches planifiées" />
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
              <th className="py-2 pr-4 font-medium">Tâche</th>
              <th className="py-2 pr-4 font-medium">Périodicité</th>
              <th className="py-2 font-medium">Dernier effet observé</th>
            </tr>
          </thead>
          <tbody>
            {health.scheduled_tasks.map((task) => (
              <tr key={task.task} className="border-b border-ink-100 last:border-0">
                <td className="py-2 pr-4 text-ink-800">{task.task}</td>
                <td className="py-2 pr-4 text-ink-600">{task.schedule}</td>
                <td className="py-2 text-ink-600">
                  {task.last_success_at
                    ? new Date(task.last_success_at).toLocaleString('fr-FR')
                    : 'Jamais'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card>
        <CardHeader title="Volumétrie" />
        <div className="grid gap-3 sm:grid-cols-3">
          {Object.entries(health.volumes).map(([key, value]) => (
            <div key={key} className="rounded-md border border-ink-200 px-4 py-3">
              <p className="text-xs uppercase tracking-wide text-ink-500">
                {VOLUME_LABELS[key] ?? key}
              </p>
              <p className="mt-1 font-display text-xl font-semibold text-ink-900">{value}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function ConfigPanel({ config }) {
  if (!config) return null
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Clés et secrets" />
        <p className="mb-3 text-sm text-ink-600">
          Présence et validité de forme uniquement. La valeur d’une clé n’est jamais affichée, ni
          consultable depuis cette interface.
        </p>
        <ul className="space-y-2">
          {config.keys.map((key) => (
            <li
              key={key.name}
              className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-ink-50 px-3 py-2"
            >
              <span>
                <span className="text-sm text-ink-800">{key.label}</span>
                <span className="ml-2 font-mono text-xs text-ink-500">{key.name}</span>
              </span>
              <Badge variant={key.present && key.valid ? 'ok' : 'critical'}>
                {!key.present ? 'Absente' : key.valid ? 'Configurée' : 'Format invalide'}
              </Badge>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <CardHeader title="Plafonds et rétention" />
        <dl className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-ink-200 px-4 py-3">
            <dt className="text-xs uppercase tracking-wide text-ink-500">Mode du fournisseur</dt>
            <dd className="mt-1 font-medium text-ink-900">{config.cti_mode}</dd>
          </div>
          <div className="rounded-md border border-ink-200 px-4 py-3">
            <dt className="text-xs uppercase tracking-wide text-ink-500">
              Emplacements de surveillance
            </dt>
            <dd className="mt-1 font-medium text-ink-900">{config.caps.monitored_slots}</dd>
          </div>
          <div className="rounded-md border border-ink-200 px-4 py-3">
            <dt className="text-xs uppercase tracking-wide text-ink-500">Analyses par mois</dt>
            <dd className="mt-1 font-medium text-ink-900">{config.caps.monthly_scans}</dd>
          </div>
          <div className="rounded-md border border-ink-200 px-4 py-3">
            <dt className="text-xs uppercase tracking-wide text-ink-500">
              Conservation des mots de passe
            </dt>
            <dd className="mt-1 font-medium text-ink-900">{config.retention.secret_days} jours</dd>
          </div>
        </dl>
      </Card>
    </div>
  )
}

function AuditPanel({ audit }) {
  if (!audit) return null
  return (
    <Card>
      <CardHeader title="Journal consolidé" />
      <p className="mb-4 text-sm text-ink-600">
        Actions d’administration et révélations de secrets. Les administrateurs plateforme ne sont
        pas au-dessus de l’audit.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
              <th className="py-2 pr-4 font-medium">Date</th>
              <th className="py-2 pr-4 font-medium">Auteur</th>
              <th className="py-2 pr-4 font-medium">Action</th>
              <th className="py-2 pr-4 font-medium">Client</th>
              <th className="py-2 font-medium">Détail</th>
            </tr>
          </thead>
          <tbody>
            {audit.entries.map((entry, index) => (
              <tr key={`${entry.at}-${index}`} className="border-b border-ink-100 last:border-0">
                <td className="py-2 pr-4 text-ink-500">
                  {new Date(entry.at).toLocaleString('fr-FR')}
                </td>
                <td className="py-2 pr-4 text-ink-800">{entry.actor || '—'}</td>
                <td className="py-2 pr-4">
                  <Badge variant={entry.kind === 'reveal' ? 'warning' : 'neutral'}>
                    {entry.action}
                  </Badge>
                </td>
                <td className="py-2 pr-4 text-ink-600">{entry.tenant || '—'}</td>
                <td className="py-2 text-ink-600">{entry.detail || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export default function PlatformAdminPage() {
  const { showToast } = useToast()
  const [activeTab, setActiveTab] = useState('capacity')
  const [loading, setLoading] = useState(true)
  const [capacity, setCapacity] = useState(null)
  const [tenants, setTenants] = useState([])
  const [plans, setPlans] = useState([])
  const [health, setHealth] = useState(null)
  const [config, setConfig] = useState(null)
  const [audit, setAudit] = useState(null)
  const [demoRequests, setDemoRequests] = useState(null)
  const [busyId, setBusyId] = useState(null)

  // La sonde de santé interroge Celery et met quelques secondes : elle est
  // chargée SÉPARÉMENT, sans bloquer le reste. L'exploitant ouvre cette page
  // d'abord pour voir ses ressources rares, pas pour attendre un ping.
  const loadCore = useCallback(async () => {
    const [capacityRes, tenantsRes, plansRes, configRes, auditRes, demoRes] =
      await Promise.all([
        platformApi.capacity(),
        platformApi.listTenants(),
        platformApi.listPlans(),
        platformApi.configuration(),
        platformApi.audit(),
        platformApi.listDemoRequests(),
      ])
    setCapacity(capacityRes.data)
    setTenants(tenantsRes.data)
    setPlans(plansRes.data)
    setConfig(configRes.data)
    setAudit(auditRes.data)
    setDemoRequests(demoRes.data)
  }, [])

  const loadHealth = useCallback(async () => {
    const response = await platformApi.health()
    setHealth(response.data)
  }, [])

  const loadAll = useCallback(async () => {
    await Promise.all([loadCore(), loadHealth().catch(() => setHealth(null))])
  }, [loadCore, loadHealth])

  useEffect(() => {
    loadCore()
      .catch(() =>
        showToast({ type: 'error', message: 'Impossible de charger l’administration.' })
      )
      .finally(() => setLoading(false))
    loadHealth().catch(() => setHealth(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleSubscriptionAction(tenantId, action) {
    setBusyId(tenantId)
    try {
      await platformApi.subscriptionAction(tenantId, { action })
      await loadAll()
      showToast({ type: 'success', message: 'Abonnement mis à jour.' })
    } catch (err) {
      // 409 = la plateforme ne peut pas honorer l'opération. Le message du
      // serveur dit ce qui reste et ce qu'il faudrait libérer : on l'affiche
      // tel quel plutôt que de le résumer.
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'L’opération a échoué.',
      })
    } finally {
      setBusyId(null)
    }
  }

  async function handleConvertDemoRequest(demoRequestId) {
    setBusyId(demoRequestId)
    try {
      const response = await platformApi.convertDemoRequest(demoRequestId)
      await loadAll()
      showToast({
        type: 'success',
        message: `${response.data.name} créée, essai ouvert.`,
      })
    } catch (err) {
      // 409 = la conversion engagerait plus d'emplacements que la plateforme
      // n'en a. Le message du serveur dit ce qui reste : on l'affiche tel quel.
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'La conversion a échoué.',
      })
    } finally {
      setBusyId(null)
    }
  }

  async function handleDemoRequestStatus(demoRequestId, nextStatus) {
    setBusyId(demoRequestId)
    try {
      await platformApi.updateDemoRequest(demoRequestId, { status: nextStatus })
      await loadCore()
    } catch {
      showToast({ type: 'error', message: 'La demande n’a pas pu être mise à jour.' })
    } finally {
      setBusyId(null)
    }
  }

  async function handleTogglePlan(code, nextStatus) {
    setBusyId(code)
    try {
      await platformApi.updatePlan(code, { status: nextStatus })
      await loadAll()
      showToast({ type: 'success', message: 'Offre mise à jour.' })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'L’offre n’a pas pu être mise à jour.',
      })
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Le titre et les onglets restent affichés pendant le chargement : la
          sonde de santé interroge Celery et prend quelques secondes, et une
          page entièrement remplacée par des squelettes ne dit même pas où
          l'on se trouve. */}
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">
          Administration de la plateforme
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Clients, offres et ressources partagées. Cet espace ne donne pas accès aux
          compromissions des clients.
        </p>
      </div>

      <Tabs tabs={TABS} activeId={activeTab} onChange={setActiveTab} />

      {loading && (
        <div className="space-y-4">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {!loading && activeTab === 'capacity' && <CapacityPanel data={capacity} />}
      {!loading && activeTab === 'tenants' && (
        <TenantsPanel
          tenants={tenants}
          onAction={handleSubscriptionAction}
          busyId={busyId}
        />
      )}
      {!loading && activeTab === 'demo' && (
        <DemoRequestsPanel
          demoRequests={demoRequests}
          onConvert={handleConvertDemoRequest}
          onSetStatus={handleDemoRequestStatus}
          busyId={busyId}
        />
      )}
      {!loading && activeTab === 'plans' && (
        <PlansPanel plans={plans} onToggleStatus={handleTogglePlan} busyCode={busyId} />
      )}
      {!loading && activeTab === 'health' && (health ? <HealthPanel health={health} /> : <SkeletonCard />)}
      {!loading && activeTab === 'config' && <ConfigPanel config={config} />}
      {!loading && activeTab === 'audit' && <AuditPanel audit={audit} />}
    </div>
  )
}
