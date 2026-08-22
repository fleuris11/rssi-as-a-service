import {
  Activity,
  Building2,
  ClipboardList,
  Gauge,
  Settings,
  ShieldCheck,
  Tags,
  Trash2,
  Users,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../api/endpoints'
import GlobalSearch from '../../components/admin/GlobalSearch'
import Badge from '../../components/ui/Badge'
import Card, { CardHeader } from '../../components/ui/Card'
import { SkeletonCard } from '../../components/ui/Skeleton'
import Tabs from '../../components/ui/Tabs'
import { useToast } from '../../components/ui/Toast'
import ClientsPanel from './panels/ClientsPanel'
import PlansPanel from './panels/PlansPanel'
import { AdminsPanel, SettingsPanel, TrashPanel } from './panels/PlatformPanel'
import ProspectsPanel from './panels/ProspectsPanel'

const TABS = [
  { id: 'capacity', label: 'Ressources', icon: Gauge },
  { id: 'tenants', label: 'Clients', icon: Building2 },
  { id: 'prospects', label: 'Prospects', icon: Users },
  { id: 'plans', label: 'Offres', icon: Tags },
  { id: 'admins', label: 'Administrateurs', icon: ShieldCheck },
  { id: 'settings', label: 'Réglages', icon: Settings },
  { id: 'trash', label: 'Corbeille', icon: Trash2 },
  { id: 'health', label: 'Santé', icon: Activity },
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
  // Pré-remplissage du formulaire de création quand on convertit un prospect :
  // retaper des informations déjà saisies est le meilleur moyen d'en perdre.
  const [clientPrefill, setClientPrefill] = useState(null)
  const [focusedTenant, setFocusedTenant] = useState(null)

  // La sonde de santé interroge Celery et met quelques secondes : elle est
  // chargée SÉPARÉMENT, sans bloquer le reste. L'exploitant ouvre cette page
  // d'abord pour voir ses ressources rares, pas pour attendre un ping.
  const loadCore = useCallback(async () => {
    const [capacityRes, tenantsRes, plansRes, configRes, auditRes] = await Promise.all([
      platformApi.capacity(),
      platformApi.listTenants(),
      platformApi.listPlans(),
      platformApi.configuration(),
      platformApi.audit(),
    ])
    setCapacity(capacityRes.data)
    setTenants(tenantsRes.data)
    setPlans(plansRes.data)
    setConfig(configRes.data)
    setAudit(auditRes.data)
  }, [])

  const loadHealth = useCallback(async () => {
    const response = await platformApi.health()
    setHealth(response.data)
  }, [])

  useEffect(() => {
    loadCore()
      .catch(() =>
        showToast({ type: 'error', message: 'Impossible de charger l’administration.' })
      )
      .finally(() => setLoading(false))
    loadHealth().catch(() => setHealth(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /** Conversion d'un prospect : on bascule sur l'écran Clients avec le
   *  formulaire déjà rempli, et le lien prospect → client est conservé. */
  function convertProspect(prospect) {
    setClientPrefill({
      name: prospect.company,
      owner_email: prospect.email,
      owner_first_name: (prospect.full_name || '').split(' ')[0] || '',
      owner_last_name: (prospect.full_name || '').split(' ').slice(1).join(' '),
      contact_phone: prospect.phone || '',
      prospect_id: prospect.id,
    })
    setActiveTab('tenants')
  }

  return (
    <div className="space-y-6">
      {/* Le titre et les onglets restent affichés pendant le chargement : la
          sonde de santé interroge Celery et prend quelques secondes, et une
          page entièrement remplacée par des squelettes ne dit même pas où
          l'on se trouve. */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-900">
            Administration de la plateforme
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Clients, offres et ressources partagées. Cet espace ne donne pas accès aux
            compromissions des clients.
          </p>
        </div>
        <div className="w-full max-w-md">
          <div className="rounded-md bg-brand-900 p-1">
            <GlobalSearch
              onSelectTenant={(id) => {
                setFocusedTenant(id)
                setActiveTab('tenants')
              }}
              onSelectProspect={() => setActiveTab('prospects')}
            />
          </div>
        </div>
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
        <ClientsPanel
          key={focusedTenant || 'liste'}
          tenants={tenants}
          plans={plans}
          onRefresh={loadCore}
          prefill={clientPrefill}
          onPrefillConsumed={() => setClientPrefill(null)}
          initialTenantId={focusedTenant}
          onFocusConsumed={() => setFocusedTenant(null)}
        />
      )}
      {!loading && activeTab === 'prospects' && (
        <ProspectsPanel onConvertToClient={convertProspect} />
      )}
      {!loading && activeTab === 'plans' && (
        <PlansPanel plans={plans} featureCatalog={config?.features || []} onRefresh={loadCore} />
      )}
      {!loading && activeTab === 'admins' && <AdminsPanel />}
      {!loading && activeTab === 'settings' && <SettingsPanel configuration={config} />}
      {!loading && activeTab === 'trash' && <TrashPanel onRefresh={loadCore} />}
      {!loading && activeTab === 'health' && (health ? <HealthPanel health={health} /> : <SkeletonCard />)}
      {!loading && activeTab === 'audit' && <AuditPanel audit={audit} />}
    </div>
  )
}
