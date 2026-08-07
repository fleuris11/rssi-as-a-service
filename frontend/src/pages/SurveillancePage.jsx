import { Globe, Mail, Plus, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { monitoringApi } from '../api/endpoints'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import Modal from '../components/ui/Modal'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

const STATUS_BADGE_VARIANT = { ok: 'ok', warning: 'warning', critical: 'critical' }
const STATUS_LABEL = { ok: 'OK', warning: 'Avertissement', critical: 'Critique' }
const STATUS_DOT_COLOR = { ok: 'bg-ok-strong', warning: 'bg-warning-strong', critical: 'bg-critical-strong' }

const ASSET_TYPE_OPTIONS = [
  { value: 'website', label: 'Site web' },
  { value: 'email_domain', label: 'Domaine email' },
]

const CHECK_TYPE_LABELS = {
  http_uptime: 'Disponibilité',
  ssl_certificate: 'Certificat SSL',
  security_headers: 'En-têtes de sécurité',
  email_dns: 'SPF / DMARC',
}

const ALERT_TYPE_LABELS = {
  down: 'Site indisponible',
  ssl_expiring: 'Certificat SSL bientôt expiré',
  security_headers: 'En-têtes de sécurité manquants',
  email_misconfigured: 'Configuration email incomplète',
}

function overallStatus(row) {
  if (row.open_alerts.some((a) => a.severity === 'critical')) return 'critical'
  if (row.open_alerts.length > 0) return 'warning'
  const statuses = Object.values(row.latest_checks)
    .filter(Boolean)
    .map((c) => c.status)
  if (statuses.includes('critical')) return 'critical'
  if (statuses.includes('warning')) return 'warning'
  if (statuses.length === 0) return null
  return 'ok'
}

function StatusBadge({ status }) {
  if (!status) {
    return <Badge variant="neutral">En attente</Badge>
  }
  return (
    <Badge variant={STATUS_BADGE_VARIANT[status]} dot>
      {STATUS_LABEL[status]}
    </Badge>
  )
}

function UptimeHistory({ history }) {
  if (!history || history.length === 0) {
    return <p className="text-xs text-ink-500">Pas encore de données.</p>
  }
  const ordered = [...history].reverse()
  return (
    <div className="flex items-center gap-0.5">
      {ordered.map((check) => (
        <span
          key={check.id}
          title={`${STATUS_LABEL[check.status]} — ${new Date(check.checked_at).toLocaleString('fr-FR')}`}
          className={`h-4 w-1.5 rounded-sm ${STATUS_DOT_COLOR[check.status]}`}
        />
      ))}
    </div>
  )
}

function NewAssetForm({ onCreated }) {
  const [type, setType] = useState('website')
  const [value, setValue] = useState('')
  const [ownershipConfirmed, setOwnershipConfirmed] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await monitoringApi.createAsset({ type, value, ownership_confirmed: ownershipConfirmed })
      setValue('')
      setOwnershipConfirmed(false)
      onCreated()
    } catch (err) {
      const data = err.response?.data
      setError(data?.detail || data?.value?.[0] || 'Impossible d’ajouter cet actif.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-ink-700" htmlFor="asset-type">
          Type
        </label>
        <select
          id="asset-type"
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="transition-smooth mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600"
        >
          {ASSET_TYPE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-ink-700" htmlFor="asset-value">
          {type === 'website' ? 'URL (https://...)' : 'Domaine (exemple.fr)'}
        </label>
        <input
          id="asset-value"
          required
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={type === 'website' ? 'https://exemple.fr' : 'exemple.fr'}
          className="transition-smooth mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600"
        />
      </div>
      <label className="flex items-start gap-2 text-xs text-ink-600">
        <input
          type="checkbox"
          checked={ownershipConfirmed}
          onChange={(e) => setOwnershipConfirmed(e.target.checked)}
          className="mt-0.5"
        />
        Je certifie être propriétaire de cet actif ou autorisé à le déclarer pour surveillance
        (vérifications passives uniquement : disponibilité, certificat, en-têtes, DNS public).
      </label>
      {error && (
        <p className="text-sm text-critical-strong" role="alert">
          {error}
        </p>
      )}
      <Button type="submit" variant="primary" loading={submitting} disabled={!ownershipConfirmed} className="w-full">
        Ajouter
      </Button>
    </form>
  )
}

export default function SurveillancePage() {
  const { showToast } = useToast()
  const [dashboard, setDashboard] = useState([])
  const [histories, setHistories] = useState({})
  const [loading, setLoading] = useState(true)
  const [updatingId, setUpdatingId] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await monitoringApi.dashboard()
      setDashboard(response.data)

      const websiteAssets = response.data.filter((row) => row.asset.type === 'website')
      const historyEntries = await Promise.all(
        websiteAssets.map(async (row) => {
          const historyRes = await monitoringApi.assetCheckHistory(row.asset.id, 'http_uptime')
          return [row.asset.id, historyRes.data.results]
        })
      )
      setHistories(Object.fromEntries(historyEntries))
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

  async function toggleActive(asset) {
    setUpdatingId(asset.id)
    try {
      await monitoringApi.updateAsset(asset.id, { is_active: !asset.is_active })
      await load()
    } catch {
      showToast({ type: 'error', message: 'La mise à jour n’a pas pu être enregistrée.' })
    } finally {
      setUpdatingId(null)
    }
  }

  async function removeAsset(asset) {
    setUpdatingId(asset.id)
    try {
      await monitoringApi.deleteAsset(asset.id)
      await load()
    } catch {
      showToast({ type: 'error', message: 'La suppression n’a pas pu être effectuée.' })
    } finally {
      setUpdatingId(null)
    }
  }

  const openAlertsCount = dashboard.reduce((sum, row) => sum + row.open_alerts.length, 0)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-900">Surveillance</h1>
          <p className="mt-1 text-sm text-ink-500">
            {openAlertsCount === 0
              ? 'Aucune alerte ouverte.'
              : `${openAlertsCount} alerte${openAlertsCount > 1 ? 's' : ''} ouverte${openAlertsCount > 1 ? 's' : ''}.`}
          </p>
        </div>
        <Button variant="primary" icon={Plus} onClick={() => setModalOpen(true)}>
          Déclarer un actif
        </Button>
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Déclarer un actif">
        <NewAssetForm
          onCreated={() => {
            setModalOpen(false)
            load()
          }}
        />
      </Modal>

      {loading ? (
        <div className="space-y-4">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : dashboard.length === 0 ? (
        <EmptyState
          icon={Globe}
          title="Aucun actif déclaré"
          description="Déclarez un site web ou un domaine email pour activer la météo cyber quotidienne."
          action={
            <Button variant="primary" icon={Plus} onClick={() => setModalOpen(true)}>
              Déclarer un actif
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          {dashboard.map((row) => {
            const status = overallStatus(row)
            const TypeIcon = row.asset.type === 'website' ? Globe : Mail
            return (
              <Card key={row.asset.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-700">
                      <TypeIcon className="size-5" aria-hidden="true" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-ink-800">{row.asset.value}</p>
                        <StatusBadge status={status} />
                      </div>
                      <p className="mt-0.5 text-xs text-ink-500">
                        {row.asset.type === 'website' ? 'Site web' : 'Domaine email'}
                        {row.uptime_24h != null && ` — disponibilité 24h : ${row.uptime_24h} %`}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={updatingId === row.asset.id}
                      onClick={() => toggleActive(row.asset)}
                    >
                      {row.asset.is_active ? 'Suspendre' : 'Réactiver'}
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      icon={Trash2}
                      disabled={updatingId === row.asset.id}
                      onClick={() => removeAsset(row.asset)}
                      aria-label={`Supprimer ${row.asset.value}`}
                    />
                  </div>
                </div>

                {row.asset.type === 'website' && (
                  <div className="mt-4">
                    <p className="mb-1 text-xs text-ink-500">Historique de disponibilité (24 dernières vérifications)</p>
                    <UptimeHistory history={histories[row.asset.id]} />
                  </div>
                )}

                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {Object.entries(row.latest_checks).map(([checkType, result]) => (
                    <div key={checkType} className="rounded-md bg-ink-50 px-3 py-2">
                      <p className="text-[11px] text-ink-500">{CHECK_TYPE_LABELS[checkType]}</p>
                      <div className="mt-1">
                        <StatusBadge status={result?.status} />
                      </div>
                    </div>
                  ))}
                </div>

                {row.open_alerts.length > 0 && (
                  <div className="mt-4 border-t border-ink-100 pt-4">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
                      Alertes ouvertes
                    </p>
                    <ul className="space-y-2">
                      {row.open_alerts.map((alert) => (
                        <li key={alert.id} className="flex items-center gap-2 text-sm text-ink-700">
                          <Badge variant={alert.severity === 'critical' ? 'critical' : 'warning'} dot>
                            {alert.severity === 'critical' ? 'Critique' : 'Avertissement'}
                          </Badge>
                          {ALERT_TYPE_LABELS[alert.alert_type] || alert.alert_type}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
