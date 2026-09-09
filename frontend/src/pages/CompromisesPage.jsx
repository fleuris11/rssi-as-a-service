import {
  Fingerprint,
  KeyRound,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { monitoringApi, threatIntelligenceApi } from '../api/endpoints'
import FeatureGate from '../components/FeatureGate'
import OwnershipProofModal from '../components/OwnershipProofModal'
import RevealSecretModal from '../components/RevealSecretModal'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { grouperParGravite, teinteGravite } from './compromises/groupesGravite'
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

/**
 * Ce que la source renvoie, et que le produit taisait (V2-2, ADR-027).
 *
 * Rien n'est mis en forme ici : le libellé, la valeur et l'implication
 * viennent du serveur. Traduire côté écran aurait garanti qu'un jour les
 * textes divergent entre la liste, le fil d'exposition et l'email — c'est
 * exactement ce qui était arrivé à la grille tarifaire.
 *
 * Replié par défaut : sept lignes de détail sur chaque carte noieraient
 * « ce qu'il faut faire », qui reste l'information principale.
 */
function DetailsFuite({ details }) {
  const [ouvert, setOuvert] = useState(false)
  if (!details?.length) return null

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOuvert((v) => !v)}
        aria-expanded={ouvert}
        className="text-sm font-medium text-brand-600 underline underline-offset-2 hover:text-brand-700"
      >
        {ouvert ? 'Masquer le détail' : `Ce que l’on sait de plus (${details.length})`}
      </button>
      {ouvert && (
        <dl className="mt-2 space-y-2 rounded-md bg-ink-50 px-3 py-2">
          {details.map((detail) => (
            <div key={detail.label}>
              <dt className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                {detail.label}
              </dt>
              <dd className="text-sm text-ink-800">{detail.value}</dd>
              {/* La valeur seule informe ; l'implication permet de décider.
                  « Raccoon » ne dit rien à un dirigeant. */}
              <dd className="text-xs text-ink-500">{detail.implication}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

function FindingCard({ finding, onUpdateStatus, updating, canReveal, onReveal }) {
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {/* La pastille portait `bg-critical-subtle` sur TOUTES les cartes :
              une fuite « Élevée » s'annonçait en rouge critique. La teinte
              suit désormais la gravité réelle, depuis la même échelle que les
              scores d'exposition. */}
          <div
            className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md"
            style={{ color: teinteGravite(finding.severity), backgroundColor: `color-mix(in srgb, ${teinteGravite(finding.severity)} 12%, white)` }}
          >
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
              {/* V2-2 (ADR-027) : UN seul champ. C'est le serveur qui décide
                  ce qu'il contient selon le rôle du lecteur — le client ne
                  reçoit plus les deux formes et n'a donc rien à arbitrer.
                  L'arbitrage côté écran, c'est une garde qui saute au premier
                  composant qui oublie de la refaire. */}
              {finding.identifier && ` — ${finding.identifier}`}
              {finding.breach_date && ` — fuite du ${new Date(finding.breach_date).toLocaleDateString('fr-FR')}`}
            </p>
          </div>
        </div>
        {/* UNE seule action forte par carte. Il y en avait trois de poids
            voisin — deux boutons bordés et un bouton plein — répétées sur
            chaque fuite : le regard ne savait plus laquelle était le chemin
            normal. « Marquer traité » est la résolution, donc la seule
            remplie ; révéler un mot de passe est une action d'enquête et
            ignorer est un abandon, tous deux en texte seul.
            L'ordre de lecture suit l'importance : enquêter, abandonner, puis
            résoudre en bout de ligne. */}
        <div className="flex shrink-0 items-center gap-1">
          {finding.has_secret && canReveal && (
            <Button variant="ghost" size="sm" icon={KeyRound} onClick={() => onReveal(finding.id)}>
              Révéler le mot de passe
            </Button>
          )}
          {finding.status === 'open' && (
            <>
              <Button
                variant="ghost"
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
      {finding.impact && (
        <p className="mt-2 rounded-md bg-ink-50 px-3 py-2 text-sm text-ink-700">
          <span className="font-semibold">Ce que ça implique : </span>
          {finding.impact}
        </p>
      )}
      <DetailsFuite details={finding.details} />
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
      {/* Le quota affiché est CELUI DU CLIENT, tiré de son offre.
          Cette barre montrait auparavant « Quota de requêtes restant
          (plateforme) : 971 » — le budget partagé par tous les clients. Un
          nombre qui ne veut rien dire pour celui qui le lit, qui bouge sans
          qu'il ait rien fait, et qui publie surtout la consommation des
          autres. Les plafonds de plateforme continuent de s'appliquer côté
          serveur ; ils n'ont pas à se raconter ici. */}
      <div className="text-sm text-ink-600">
        <p>
          Analyses restantes ce mois :{' '}
          <span className="font-medium text-ink-900">
            {status.scans_remaining ?? 'illimitées'}
          </span>
          {status.scans_quota ? (
            <span className="text-ink-500"> sur {status.scans_quota} comprises dans votre offre</span>
          ) : null}
        </p>
        {/* `cooldown_hours` n'existe plus : le délai est réglable en minutes
            depuis la fiche client, et le serveur envoie une phrase déjà
            formée (« 30 minutes », « 1 h 30 »). L'ancien champ affichait
            « d’ici  h ». */}
        {status.cooldown_active && !scanning && (
          <p className="mt-1 text-xs text-warning-strong">
            Une analyse a déjà été lancée récemment pour votre entreprise. Une nouvelle sera
            possible d’ici {status.cooldown_label} — les fuites détectées entre-temps vous
            parviennent sans attendre.
          </p>
        )}
        {/* Ce que le client demandait sans l'obtenir : est-ce que ça tourne
            encore, et est-ce que ça s'arrête si je vais ailleurs. */}
        {scanning && (
          <p className="mt-1 text-xs text-ink-500">
            L’analyse se poursuit sur nos serveurs, même si vous quittez cette page ou fermez
            votre navigateur. Revenez quand vous voulez : le résultat vous attendra ici.
          </p>
        )}
        {!scanning && status.last_scan_finished_at && (
          <p className="mt-1 text-xs text-ink-500">
            Dernière analyse terminée le{' '}
            {new Date(status.last_scan_finished_at).toLocaleString('fr-FR', {
              dateStyle: 'long',
              timeStyle: 'short',
            })}
            .
          </p>
        )}
      </div>
      <Button variant="primary" icon={RefreshCw} loading={scanning} disabled={disabled} onClick={onScan}>
        {scanning ? 'Analyse en cours…' : 'Lancer un scan'}
      </Button>
    </Card>
  )
}

/**
 * Panneau d'administration : même page, poids visuel inférieur.
 *
 * « Surveillance en temps réel » et « Journal des révélations » portaient la
 * même carte blanche ombrée que les fuites elles-mêmes. Sur une page dont la
 * matière est la gravité, deux blocs de réglage ne doivent pas peser autant
 * que dix compromissions : fond transparent, pas d'ombre, un filet en haut, et
 * un titre en surtitre plutôt qu'en titre de section.
 */
function PanneauSecondaire({ titre, action, children }) {
  return (
    <section className="border-t border-ink-200 pt-5">
      <div className="mb-3 flex items-start justify-between gap-4">
        <h2 className="t-eyebrow">{titre}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function MonitoredAssetsPanel({
  assets,
  monitored,
  onRegister,
  onUnregister,
  onProveOwnership,
  statut,
  busyId,
}) {
  const monitoredAssetIds = new Set(monitored.map((m) => m.asset_id))
  const registrable = assets.filter((a) => !monitoredAssetIds.has(a.id))

  return (
    <PanneauSecondaire
      titre="Surveillance en temps réel"
      action={
        statut?.monitored_quota ? (
          <span className="t-meta">
            {statut.monitored_used} / {statut.monitored_quota} inclus dans votre offre
          </span>
        ) : null
      }
    >
      {/* « 0 / 15 emplacements utilisés » et « pour toute la plateforme »
          disaient au client la taille de notre licence et ce que les autres
          en consomment. Ce qui le concerne, c'est ce que SON offre comprend. */}
      <p className="mb-4 text-sm text-ink-500">
        Les actifs surveillés en temps réel reçoivent une alerte immédiate en cas de nouvelle
        compromission détectée, sans consommer vos analyses mensuelles.
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
                  {/* ADR-026 : la surveillance continue exige une possession
                      PROUVÉE. Proposer « Surveiller » sur un actif non prouvé
                      mènerait droit à un refus — autant nommer d'emblée
                      l'étape qui manque. L'analyse ponctuelle, elle, reste
                      accessible : rien n'est retiré au client. */}
                  {asset.ownership_state === 'proven' ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={busyId === asset.id}
                      onClick={() => onRegister(asset.id)}
                    >
                      Surveiller
                    </Button>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={busyId === asset.id}
                      onClick={() => onProveOwnership(asset)}
                    >
                      Prouver la possession
                    </Button>
                  )}
                </FeatureGate>
              </li>
            ))}
          </ul>
        </div>
      )}
    </PanneauSecondaire>
  )
}

function RevealAuditPanel({ audits, onLoad, loading }) {
  return (
    <PanneauSecondaire
      titre="Journal des révélations"
      action={
        <Button variant="ghost" size="sm" onClick={onLoad} loading={loading}>
          {audits === null ? 'Afficher' : 'Actualiser'}
        </Button>
      }
    >
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
    </PanneauSecondaire>
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
  // V2-1 : ce que la dernière analyse a revu sans le remonter dans la liste.
  // Une fuite déjà traitée n'y réapparaît plus — mais la taire complètement
  // laisserait croire que le fournisseur ne la remonte plus. On masque, on ne
  // cache pas.
  const [dejaTraiteesRevues, setDejaTraiteesRevues] = useState(0)
  const [updatingId, setUpdatingId] = useState(null)
  const [busyAssetId, setBusyAssetId] = useState(null)
  const [revealFindingId, setRevealFindingId] = useState(null)
  const [ownershipAsset, setOwnershipAsset] = useState(null)
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

  // Un seul endroit décide de ce qui se dit quand une analyse se termine —
  // qu'elle ait été lancée dans cet onglet ou retrouvée en cours au
  // chargement de la page.
  const onScanSettled = useCallback(
    async (job) => {
      setScanning(false)
      if (job.status === 'done') {
        const created = job.result_ref?.findings_created ?? 0
        setDejaTraiteesRevues(job.result_ref?.already_treated_seen ?? 0)
        showToast({
          type: 'success',
          message:
            created > 0
              ? `Analyse terminée : ${created} nouvelle${created > 1 ? 's' : ''} compromission${created > 1 ? 's' : ''} détectée${created > 1 ? 's' : ''}.`
              : 'Analyse terminée : aucune nouvelle compromission détectée.',
        })
        await loadAll()
      } else {
        showToast({ type: 'error', message: 'L’analyse a échoué. Réessayez plus tard.' })
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  )

  // Reprise d'une analyse déjà en cours. Le job tourne dans un worker : il
  // survit au changement de page, au rechargement et à la fermeture du
  // navigateur. Seul l'écran l'oubliait, parce que `scanning` ne vivait que
  // dans ce composant — le client revenait, ne voyait plus rien, relançait,
  // et se heurtait au délai anti-abus.
  useEffect(() => {
    if (status?.running_scan_id && !scanning) {
      setScanning(true)
      poll(status.running_scan_id, onScanSettled)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.running_scan_id])

  async function handleScan() {
    setScanning(true)
    try {
      const response = await threatIntelligenceApi.triggerScan()
      poll(response.data.id, onScanSettled)
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

      {dejaTraiteesRevues > 0 && activeTab !== 'treated' && (
        <p className="-mt-2 text-sm text-ink-500">
          La dernière analyse a revu{' '}
          <strong className="font-medium text-ink-700">
            {dejaTraiteesRevues} compromission{dejaTraiteesRevues > 1 ? 's' : ''}
          </strong>{' '}
          que vous aviez déjà traitée{dejaTraiteesRevues > 1 ? 's' : ''} ou ignorée
          {dejaTraiteesRevues > 1 ? 's' : ''}. Elle{dejaTraiteesRevues > 1 ? 's' : ''} ne
          revien{dejaTraiteesRevues > 1 ? 'nent' : 't'} pas dans cette liste.{' '}
          <button
            type="button"
            onClick={() => setActiveTab('treated')}
            className="font-medium text-brand-600 underline underline-offset-2 hover:text-brand-700"
          >
            Les consulter
          </button>
        </p>
      )}

      {findings.length === 0 ? (
        activeTab === 'open' ? (
          // Une absence de fuite n'est pas une absence de données : c'est le
          // résultat que le client paie pour obtenir. Il était écrit en gris,
          // sous un pictogramme d'alerte, et se lisait comme une panne.
          <EmptyState
            tone="positive"
            icon={ShieldCheck}
            title="Aucune fuite en cours"
            description="Rien à traiter sur vos actifs surveillés. La surveillance continue en arrière-plan : vous serez prévenu dès qu’un élément apparaît."
          />
        ) : (
          <EmptyState
            icon={ShieldAlert}
            title={activeTab === 'treated' ? 'Rien de traité pour l’instant' : 'Rien d’ignoré'}
            description={
              activeTab === 'treated'
                ? 'Les compromissions que vous marquerez comme traitées se retrouveront ici.'
                : 'Les compromissions que vous choisirez d’ignorer se retrouveront ici.'
            }
          />
        )
      ) : (
        // Regroupement par gravité, avec le compte dans le séparateur. La
        // liste arrivait à plat et le serveur ne garantit pas l'ordre : sur le
        // jeu de démonstration, une fuite critique se lisait après quatre
        // fuites élevées. Le compte appartient au séparateur — c'est là qu'on
        // décide si on lit la suite.
        <div className="space-y-8">
          {grouperParGravite(findings).map((groupe) => (
            <section key={groupe.severite} aria-labelledby={`gravite-${groupe.severite}`}>
              <div className="mb-3 flex items-center gap-3">
                <span
                  className="size-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: groupe.teinte }}
                  aria-hidden="true"
                />
                <h2 id={`gravite-${groupe.severite}`} className="t-eyebrow">
                  {groupe.libelle}
                </h2>
                <span className="h-px flex-1 bg-ink-200" aria-hidden="true" />
              </div>
              <div className="space-y-4">
                {groupe.findings.map((finding) => (
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
            </section>
          ))}
        </div>
      )}

      <MonitoredAssetsPanel
        assets={assets}
        monitored={monitored}
        onRegister={handleRegister}
        onProveOwnership={setOwnershipAsset}
        onUnregister={handleUnregister}
        statut={status}
        busyId={busyAssetId}
      />

      {isTenantAdmin && (
        <RevealAuditPanel audits={revealAudits} onLoad={loadRevealAudits} loading={loadingAudits} />
      )}

      <OwnershipProofModal
        open={ownershipAsset !== null}
        asset={ownershipAsset}
        onClose={() => setOwnershipAsset(null)}
        onProven={loadAll}
      />

      <RevealSecretModal
        open={revealFindingId !== null}
        findingId={revealFindingId}
        onClose={() => setRevealFindingId(null)}
      />
    </div>
  )
}
