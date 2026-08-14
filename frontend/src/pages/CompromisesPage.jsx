import { AlertTriangle, Fingerprint, KeyRound, RefreshCw, ShieldAlert, ShieldOff } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { monitoringApi, threatIntelligenceApi } from '../api/endpoints'
import FeatureGate from '../components/FeatureGate'
import RevealSecretModal from '../components/RevealSecretModal'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card, { CardHeader } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonCard } from '../components/ui/Skeleton'
import Tabs from '../components/ui/Tabs'
import { useToast } from '../components/ui/Toast'
import { useAuth } from '../context/AuthContext'

const SEVERITY_LABEL = { critical: 'Critique', high: 'Élevée', attention: 'Attention' }
const SEVERITY_VARIANT = { critical: 'critical', high: 'critical', attention: 'warning' }

const SOURCE_LABELS = {
  stealer: "Logs de malware voleur d'identifiants",
  combo: 'Liste combo (identifiant + mot de passe)',
  creds: 'Identifiants exposés',
  sessions: 'Sessions / cookies compromis',
  nhi: 'Identité non-humaine (clé, jeton)',
  darkweb: 'Mention dark web',
  docs: 'Document fuité',
  asm: "Surface d'attaque",
  radar: 'Radar (mentions publiques)',
  webhook: 'Notification temps réel',
}

// Phase 8B : la vulgarisation ne vit plus ici. Elle est calculée côté
// serveur (apps/threat_intelligence/plain_language.py) et renvoyée par
// l'API sur chaque finding (`meaning` / `recommended_action`), pour que le
// texte lu par le dirigeant soit identique partout — page Exposition, liste
// Compromissions, email de notification — au lieu d'exister en double ici
// et là, avec le risque de diverger silencieusement.

const TABS = [
  { id: 'open', label: 'Ouvertes' },
  { id: 'treated', label: 'Traitées' },
  { id: 'ignored', label: 'Ignorées' },
]

function usePolling(fetchJob) {
  const timeoutRef = useRef(null)
  useEffect(() => () => clearTimeout(timeoutRef.current), [])

  return useCallback(
    (jobId, onSettled) => {
      async function tick() {
        try {
          const response = await fetchJob(jobId)
          if (response.data.status === 'done' || response.data.status === 'failed') {
            onSettled(response.data)
            return
          }
        } catch {
          // Hiccup réseau ponctuel — le job existe toujours côté serveur, on continue.
        }
        timeoutRef.current = setTimeout(tick, 2000)
      }
      tick()
    },
    [fetchJob]
  )
}

function FindingCard({ finding, onUpdateStatus, updating, canReveal, onReveal }) {
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md bg-critical-subtle text-critical-strong">
            <ShieldAlert className="size-5" aria-hidden="true" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-ink-800">{finding.asset_value}</p>
              <Badge variant={SEVERITY_VARIANT[finding.severity]} dot>
                {SEVERITY_LABEL[finding.severity]}
              </Badge>
              {finding.has_secret && (
                <Badge variant="neutral">
                  <Fingerprint className="size-3" aria-hidden="true" />
                  Secret exposé ({finding.secret_masked})
                </Badge>
              )}
            </div>
            <p className="mt-0.5 text-xs text-ink-500">
              {SOURCE_LABELS[finding.source_endpoint] || finding.source_endpoint}
              {finding.identifier_plain && ` — ${finding.identifier_plain}`}
              {!finding.identifier_plain && finding.identifier_masked && ` — ${finding.identifier_masked}`}
              {finding.breach_date && ` — fuite du ${new Date(finding.breach_date).toLocaleDateString('fr-FR')}`}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {finding.has_secret && canReveal && (
            <Button variant="secondary" size="sm" icon={KeyRound} onClick={() => onReveal(finding.id)}>
              Révéler le mot de passe
            </Button>
          )}
          {finding.status === 'open' && (
            <>
              <Button
                variant="secondary"
                size="sm"
                disabled={updating}
                onClick={() => onUpdateStatus(finding.id, 'ignored')}
              >
                Ignorer
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={updating}
                onClick={() => onUpdateStatus(finding.id, 'treated')}
              >
                Marquer traité
              </Button>
            </>
          )}
        </div>
      </div>
      <p className="mt-3 rounded-md bg-ink-50 px-3 py-2 text-sm text-ink-700">{finding.meaning}</p>
      <p className="mt-2 rounded-md bg-accent-100/50 px-3 py-2 text-sm text-accent-900">
        <span className="font-semibold">À faire : </span>
        {finding.recommended_action}
      </p>
    </Card>
  )
}

function ScanStatusBar({ status, onScan, scanning }) {
  if (!status) return null
  const disabled = scanning || status.cooldown_active
  return (
    <Card className="flex flex-wrap items-center justify-between gap-4" padding="p-4">
      <div className="text-sm text-ink-600">
        <p>
          Quota de requêtes restant (plateforme) :{' '}
          <span className="font-medium text-ink-900">
            {status.quota_remaining ?? 'inconnu'}
          </span>
        </p>
        {status.cooldown_active && (
          <p className="mt-1 text-xs text-warning-strong">
            Un scan a déjà été lancé récemment — réessayez dans quelques heures (délai anti-abus :{' '}
            {status.cooldown_hours} h).
          </p>
        )}
      </div>
      <Button variant="primary" icon={RefreshCw} loading={scanning} disabled={disabled} onClick={onScan}>
        {scanning ? 'Analyse en cours…' : 'Lancer un scan'}
      </Button>
    </Card>
  )
}

function MonitoredAssetsPanel({ assets, monitored, onRegister, onUnregister, poolStatus, busyId }) {
  const monitoredAssetIds = new Set(monitored.map((m) => m.asset_id))
  const registrable = assets.filter((a) => !monitoredAssetIds.has(a.id))

  return (
    <Card>
      <CardHeader
        title="Surveillance en temps réel"
        action={
          poolStatus && (
            <span className="text-xs text-ink-500">
              {poolStatus.pool_used} / {poolStatus.pool_capacity} slots utilisés
            </span>
          )
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Les actifs surveillés en temps réel reçoivent une alerte immédiate en cas de nouvelle
        compromission détectée (hors quota de scan mensuel), dans la limite de{' '}
        {poolStatus?.pool_capacity ?? 15} actifs pour toute la plateforme.
      </p>

      {monitored.length === 0 ? (
        <p className="mb-4 text-sm text-ink-500">Aucun actif surveillé en temps réel pour le moment.</p>
      ) : (
        <ul className="mb-4 space-y-2">
          {monitored.map((m) => (
            <li key={m.id} className="flex items-center justify-between gap-3 rounded-md bg-ink-50 px-3 py-2">
              <span className="truncate text-sm text-ink-700">{m.asset_value}</span>
              <Button
                variant="danger"
                size="sm"
                icon={ShieldOff}
                disabled={busyId === m.asset_id}
                onClick={() => onUnregister(m.asset_id)}
              >
                Retirer
              </Button>
            </li>
          ))}
        </ul>
      )}

      {registrable.length > 0 && (
        <div className="space-y-2 border-t border-ink-100 pt-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
            Ajouter un actif à la surveillance
          </p>
          <ul className="space-y-2">
            {registrable.map((asset) => (
              <li key={asset.id} className="flex items-center justify-between gap-3">
                <span className="truncate text-sm text-ink-700">{asset.value}</span>
                <FeatureGate feature="realtime_monitoring">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={busyId === asset.id}
                    onClick={() => onRegister(asset.id)}
                  >
                    Surveiller
                  </Button>
                </FeatureGate>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}

function RevealAuditPanel({ audits, onLoad, loading }) {
  return (
    <Card>
      <CardHeader
        title="Journal des révélations"
        action={
          <Button variant="secondary" size="sm" onClick={onLoad} loading={loading}>
            {audits === null ? 'Afficher' : 'Actualiser'}
          </Button>
        }
      />
      <p className="mb-3 text-xs text-ink-500">
        Chaque tentative de révélation d’un mot de passe (accordée ou refusée) est tracée ici —
        jamais le secret lui-même.
      </p>
      {audits !== null && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
                <th className="py-2 pr-4 font-medium">Utilisateur</th>
                <th className="py-2 pr-4 font-medium">Fuite</th>
                <th className="py-2 pr-4 font-medium">Résultat</th>
                <th className="py-2 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {audits.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-3 text-ink-500">
                    Aucune révélation enregistrée pour le moment.
                  </td>
                </tr>
              ) : (
                audits.map((row) => (
                  <tr key={row.id} className="border-b border-ink-100 last:border-0">
                    <td className="py-2 pr-4 text-ink-800">{row.user_email || '—'}</td>
                    <td className="py-2 pr-4 text-ink-600">
                      {row.finding_id != null ? `#${row.finding_id}` : '—'}
                    </td>
                    <td className="py-2 pr-4">
                      <Badge variant={row.success ? 'ok' : 'critical'}>
                        {row.success ? 'Accordée' : `Refusée (${row.denial_reason})`}
                      </Badge>
                    </td>
                    <td className="py-2 text-ink-500">
                      {new Date(row.created_at).toLocaleString('fr-FR')}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

export default function CompromisesPage() {
  const { showToast } = useToast()
  const { user, currentTenant } = useAuth()
  const isTenantAdmin = currentTenant?.role === 'admin'
  // Le bouton "Révéler" suit la règle serveur (admin du tenant OU admin
  // plateforme — voir BreachFindingRevealView) ; le journal d'audit du
  // tenant, lui, reste réservé au rôle admin strict (pas de bypass staff),
  // même règle que GET /audit/reveals/ côté API (IsTenantAdmin).
  const canReveal = isTenantAdmin || Boolean(user?.is_staff)
  const [loading, setLoading] = useState(true)
  const [findings, setFindings] = useState([])
  const [activeTab, setActiveTab] = useState('open')
  const [status, setStatus] = useState(null)
  const [assets, setAssets] = useState([])
  const [monitored, setMonitored] = useState([])
  const [scanning, setScanning] = useState(false)
  const [updatingId, setUpdatingId] = useState(null)
  const [busyAssetId, setBusyAssetId] = useState(null)
  const [revealFindingId, setRevealFindingId] = useState(null)
  const [revealAudits, setRevealAudits] = useState(null)
  const [loadingAudits, setLoadingAudits] = useState(false)

  const poll = usePolling(threatIntelligenceApi.getScanJob)

  const loadFindings = useCallback(
    async (tab) => {
      const response = await threatIntelligenceApi.listFindings(tab)
      setFindings(response.data.results)
    },
    []
  )

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [findingsRes, statusRes, assetsRes, monitoredRes] = await Promise.all([
        threatIntelligenceApi.listFindings(activeTab),
        threatIntelligenceApi.status(),
        monitoringApi.listAssets(),
        threatIntelligenceApi.listMonitoredAssets(),
      ])
      setFindings(findingsRes.data.results)
      setStatus(statusRes.data)
      setAssets(assetsRes.data.results)
      setMonitored(monitoredRes.data.results)
    } catch {
      showToast({
        type: 'error',
        message: 'Impossible de charger les compromissions.',
        action: { label: 'Réessayer', onClick: loadAll },
      })
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  useEffect(() => {
    if (!loading) loadFindings(activeTab)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab])

  async function handleScan() {
    setScanning(true)
    try {
      const response = await threatIntelligenceApi.triggerScan()
      poll(response.data.id, async (job) => {
        setScanning(false)
        if (job.status === 'done') {
          const created = job.result_ref?.findings_created ?? 0
          showToast({
            type: 'success',
            message:
              created > 0
                ? `Scan terminé : ${created} nouvelle${created > 1 ? 's' : ''} compromission${created > 1 ? 's' : ''} détectée${created > 1 ? 's' : ''}.`
                : 'Scan terminé : aucune nouvelle compromission détectée.',
          })
          await loadAll()
        } else {
          showToast({ type: 'error', message: 'Le scan a échoué. Réessayez plus tard.' })
        }
      })
    } catch (err) {
      setScanning(false)
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de lancer le scan.',
      })
    }
  }

  async function handleUpdateStatus(findingId, newStatus) {
    setUpdatingId(findingId)
    try {
      await threatIntelligenceApi.updateFindingStatus(findingId, newStatus)
      await loadFindings(activeTab)
      showToast({ type: 'success', message: newStatus === 'treated' ? 'Compromission marquée traitée.' : 'Compromission ignorée.' })
    } catch {
      showToast({ type: 'error', message: 'La mise à jour n’a pas pu être enregistrée.' })
    } finally {
      setUpdatingId(null)
    }
  }

  async function handleRegister(assetId) {
    setBusyAssetId(assetId)
    try {
      await threatIntelligenceApi.registerMonitoredAsset(assetId)
      await loadAll()
      showToast({ type: 'success', message: 'Surveillance en temps réel activée.' })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible d’activer la surveillance.',
      })
    } finally {
      setBusyAssetId(null)
    }
  }

  async function handleUnregister(assetId) {
    setBusyAssetId(assetId)
    try {
      await threatIntelligenceApi.unregisterMonitoredAsset(assetId)
      await loadAll()
      showToast({ type: 'success', message: 'Surveillance en temps réel retirée.' })
    } catch {
      showToast({ type: 'error', message: 'Impossible de retirer la surveillance.' })
    } finally {
      setBusyAssetId(null)
    }
  }

  async function loadRevealAudits() {
    setLoadingAudits(true)
    try {
      const response = await threatIntelligenceApi.listRevealAudit()
      setRevealAudits(response.data.results)
    } catch {
      showToast({ type: 'error', message: 'Impossible de charger le journal des révélations.' })
    } finally {
      setLoadingAudits(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Compromissions</h1>
        <p className="mt-1 text-sm text-ink-500">
          Le détail de chaque fuite avérée liée à vos actifs. Pour une lecture priorisée, voir la
          page Exposition — les signaux avant-coureurs (domaine ressemblant, mention dark web) y
          sont regroupés dans leur propre carte.
        </p>
      </div>

      <ScanStatusBar status={status} onScan={handleScan} scanning={scanning} />

      <Tabs tabs={TABS} activeId={activeTab} onChange={setActiveTab} />

      {findings.length === 0 ? (
        <EmptyState
          icon={activeTab === 'open' ? AlertTriangle : ShieldAlert}
          title={activeTab === 'open' ? 'Aucune compromission ouverte' : 'Aucun élément ici'}
          description={
            activeTab === 'open'
              ? 'Aucune fuite de données détectée pour vos actifs surveillés pour le moment.'
              : 'Les compromissions traitées ou ignorées apparaîtront ici.'
          }
        />
      ) : (
        <div className="space-y-4">
          {findings.map((finding) => (
            <FindingCard
              key={finding.id}
              finding={finding}
              onUpdateStatus={handleUpdateStatus}
              updating={updatingId === finding.id}
              canReveal={canReveal}
              onReveal={setRevealFindingId}
            />
          ))}
        </div>
      )}

      <MonitoredAssetsPanel
        assets={assets}
        monitored={monitored}
        onRegister={handleRegister}
        onUnregister={handleUnregister}
        poolStatus={status}
        busyId={busyAssetId}
      />

      {isTenantAdmin && (
        <RevealAuditPanel audits={revealAudits} onLoad={loadRevealAudits} loading={loadingAudits} />
      )}

      <RevealSecretModal
        open={revealFindingId !== null}
        findingId={revealFindingId}
        onClose={() => setRevealFindingId(null)}
      />
    </div>
  )
}
