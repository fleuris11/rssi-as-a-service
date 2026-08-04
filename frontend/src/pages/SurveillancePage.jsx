import { useCallback, useEffect, useState } from 'react'
import { monitoringApi } from '../api/endpoints'

const STATUS_COLOR = {
  ok: 'bg-emerald-500',
  warning: 'bg-amber-500',
  critical: 'bg-red-500',
}
const STATUS_LABEL = { ok: 'OK', warning: 'Avertissement', critical: 'Critique' }

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

function StatusBadge({ status }) {
  if (!status) {
    return <span className="text-xs text-slate-400">—</span>
  }
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-white ${STATUS_COLOR[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  )
}

function UptimeHistory({ history }) {
  if (!history || history.length === 0) {
    return <p className="text-xs text-slate-400">Pas encore de données.</p>
  }
  const ordered = [...history].reverse()
  return (
    <div className="flex items-center gap-0.5">
      {ordered.map((check) => (
        <span
          key={check.id}
          title={`${STATUS_LABEL[check.status]} — ${new Date(check.checked_at).toLocaleString('fr-FR')}`}
          className={`h-4 w-1.5 rounded-sm ${STATUS_COLOR[check.status]}`}
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
      await monitoringApi.createAsset({
        type,
        value,
        ownership_confirmed: ownershipConfirmed,
      })
      setValue('')
      setOwnershipConfirmed(false)
      onCreated()
    } catch (err) {
      const data = err.response?.data
      setError(data?.detail || data?.value?.[0] || "Impossible d'ajouter cet actif.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
    >
      <h2 className="text-sm font-medium text-slate-500">Déclarer un actif</h2>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div>
          <label className="block text-xs font-medium text-slate-600" htmlFor="asset-type">
            Type
          </label>
          <select
            id="asset-type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="mt-1 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            {ASSET_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className="block text-xs font-medium text-slate-600" htmlFor="asset-value">
            {type === 'website' ? 'URL (https://...)' : 'Domaine (exemple.fr)'}
          </label>
          <input
            id="asset-value"
            required
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={type === 'website' ? 'https://exemple.fr' : 'exemple.fr'}
            className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
        <button
          type="submit"
          disabled={submitting || !ownershipConfirmed}
          className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? 'Ajout…' : 'Ajouter'}
        </button>
      </div>
      <label className="mt-3 flex items-start gap-2 text-xs text-slate-600">
        <input
          type="checkbox"
          checked={ownershipConfirmed}
          onChange={(e) => setOwnershipConfirmed(e.target.checked)}
          className="mt-0.5"
        />
        Je certifie être propriétaire de cet actif ou autorisé à le déclarer pour surveillance
        (vérifications passives uniquement : disponibilité, certificat, en-têtes, DNS public).
      </label>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </form>
  )
}

export default function SurveillancePage() {
  const [dashboard, setDashboard] = useState([])
  const [histories, setHistories] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [updatingId, setUpdatingId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
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
      setError('Impossible de charger le tableau de bord.')
    } finally {
      setLoading(false)
    }
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
      setError("La mise à jour n'a pas pu être enregistrée.")
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
      setError("La suppression n'a pas pu être effectuée.")
    } finally {
      setUpdatingId(null)
    }
  }

  const openAlertsCount = dashboard.reduce((sum, row) => sum + row.open_alerts.length, 0)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Surveillance</h1>
        <p className="mt-1 text-sm text-slate-500">
          {openAlertsCount === 0
            ? 'Aucune alerte ouverte.'
            : `${openAlertsCount} alerte${openAlertsCount > 1 ? 's' : ''} ouverte${openAlertsCount > 1 ? 's' : ''}.`}
        </p>
      </div>

      <NewAssetForm onCreated={load} />

      {error && <p className="text-sm text-red-600">{error}</p>}

      {loading ? (
        <p className="text-slate-500">Chargement…</p>
      ) : dashboard.length === 0 ? (
        <p className="text-slate-600">Aucun actif déclaré pour l’instant.</p>
      ) : (
        <div className="space-y-4">
          {dashboard.map((row) => (
            <div
              key={row.asset.id}
              className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-800">{row.asset.value}</p>
                  <p className="text-xs text-slate-400">
                    {row.asset.type === 'website' ? 'Site web' : 'Domaine email'}
                    {row.uptime_24h != null && ` — disponibilité 24h : ${row.uptime_24h} %`}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={updatingId === row.asset.id}
                    onClick={() => toggleActive(row.asset)}
                    className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:border-slate-400 disabled:opacity-50"
                  >
                    {row.asset.is_active ? 'Suspendre' : 'Réactiver'}
                  </button>
                  <button
                    type="button"
                    disabled={updatingId === row.asset.id}
                    onClick={() => removeAsset(row.asset)}
                    className="rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:border-red-300 disabled:opacity-50"
                  >
                    Supprimer
                  </button>
                </div>
              </div>

              {row.asset.type === 'website' && (
                <div className="mt-3">
                  <p className="mb-1 text-xs text-slate-500">Historique de disponibilité</p>
                  <UptimeHistory history={histories[row.asset.id]} />
                </div>
              )}

              <div className="mt-3 flex flex-wrap gap-4">
                {Object.entries(row.latest_checks).map(([checkType, result]) => (
                  <div key={checkType} className="text-xs">
                    <p className="text-slate-500">{CHECK_TYPE_LABELS[checkType]}</p>
                    <StatusBadge status={result?.status} />
                  </div>
                ))}
              </div>

              {row.open_alerts.length > 0 && (
                <ul className="mt-3 space-y-1 border-t border-slate-100 pt-3">
                  {row.open_alerts.map((alert) => (
                    <li key={alert.id} className="flex items-center gap-2 text-xs text-slate-600">
                      <StatusBadge status={alert.severity === 'critical' ? 'critical' : 'warning'} />
                      {ALERT_TYPE_LABELS[alert.alert_type] || alert.alert_type}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
