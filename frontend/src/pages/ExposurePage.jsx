import {
  ChevronDown,
  ChevronRight,
  Info,
  KeyRound,
  Link2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { aiApi, threatIntelligenceApi } from '../api/endpoints'
import ExposureScoreDial from '../components/ExposureScoreDial'
import FeatureGate, { FeatureLockedNotice } from '../components/FeatureGate'
import PreIncidentRadar from '../components/PreIncidentRadar'
import RevealSecretModal from '../components/RevealSecretModal'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'
import { useAuth } from '../context/AuthContext'

const SEVERITY_VARIANT = { critical: 'critical', high: 'critical', attention: 'warning' }

function SynthesisBanner({ synthesis, onRefresh, refreshing, canRefresh }) {
  // Absent = la page reste complète : la synthèse est une couche au-dessus,
  // jamais un prérequis (pas de spinner bloquant, pas d'état d'erreur).
  if (!synthesis) {
    return canRefresh ? (
      <Card className="flex flex-wrap items-center justify-between gap-3 border-brand-200" padding="p-4">
        <div className="flex items-start gap-2">
          <Sparkles className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden="true" />
          <p className="text-sm text-ink-600">
            Obtenez une lecture d’ensemble de votre exposition, rédigée à partir des éléments
            ci-dessous.
          </p>
        </div>
        <FeatureGate feature="exposure_synthesis">
          <Button
            variant="secondary"
            size="sm"
            icon={Sparkles}
            loading={refreshing}
            onClick={onRefresh}
          >
            Générer l’analyse
          </Button>
        </FeatureGate>
      </Card>
    ) : null
  }

  return (
    <Card className="border-brand-200 bg-brand-50/50">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md bg-brand-100 text-brand-800">
            <Sparkles className="size-5" aria-hidden="true" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-display text-lg font-semibold text-ink-900">Analyse</h2>
              {synthesis.is_stale && (
                <Badge variant="warning">Antérieure à vos dernières actions</Badge>
              )}
            </div>
            <p className="mt-0.5 text-xs text-ink-500">
              Générée le {new Date(synthesis.generated_at).toLocaleString('fr-FR')}
            </p>
          </div>
        </div>
        {canRefresh && (
          <FeatureGate feature="exposure_synthesis">
            <Button
              variant="secondary"
              size="sm"
              icon={RefreshCw}
              loading={refreshing}
              onClick={onRefresh}
            >
              Actualiser l’analyse
            </Button>
          </FeatureGate>
        )}
      </div>
      <p className="mt-3 text-sm leading-relaxed text-ink-800">{synthesis.content}</p>
    </Card>
  )
}

function ScoreExplanation({ components }) {
  return (
    <div className="mt-3 rounded-md bg-ink-50 px-3 py-2">
      <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-500">
        <Info className="size-3.5" aria-hidden="true" />
        Comment ce score est calculé
      </p>
      <ul className="space-y-1">
        {components.map((component) => (
          <li key={component.finding_id} className="text-xs text-ink-600">
            {/* Une contribution arrondie à 0 est honnête (cette n-ième fuite
                ne pèse quasiment plus) mais « +0 » se lit comme un bug :
                on l'écrit en toutes lettres. */}
            <span className="font-medium text-ink-800">
              {component.points > 0 ? `+${component.points}` : 'moins de 1'}
            </span>{' '}
            — {component.label} ({component.detail})
          </li>
        ))}
      </ul>
    </div>
  )
}

function FindingRow({ finding, canReveal, onReveal, retentionDays }) {
  return (
    <li className="rounded-md border border-ink-200/70 bg-surface px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium text-ink-800">{finding.source_label}</p>
        <Badge variant={SEVERITY_VARIANT[finding.severity] || 'neutral'} dot>
          {finding.severity_label}
        </Badge>
        {/* Badge de corrélation : formulation venue du serveur, jamais
            reformulée ici — le vocabulaire « possible / à vérifier » est une
            contrainte produit, pas un choix d'affichage (ADR-017). */}
        {finding.reuse_signals?.length > 0 && (
          <Badge variant="warning">
            <Link2 className="size-3" aria-hidden="true" />
            Réutilisation possible
          </Badge>
        )}
        {finding.identifier && (
          <span className="font-mono text-xs text-ink-600">{finding.identifier}</span>
        )}
        {finding.breach_date && (
          <span className="text-xs text-ink-500">
            fuite du {new Date(finding.breach_date).toLocaleDateString('fr-FR')}
          </span>
        )}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-ink-700">{finding.meaning}</p>

      {finding.reuse_signals?.map((signal) => (
        <p
          key={signal.signal_type}
          className="mt-2 rounded-md border-l-2 border-warning-strong bg-warning-subtle px-3 py-2 text-sm text-warning-strong"
        >
          <span className="font-semibold">{signal.label} — </span>
          {signal.explanation}
        </p>
      ))}

      <div className="mt-2 flex flex-wrap items-start justify-between gap-2 rounded-md bg-accent-100/50 px-3 py-2">
        <p className="text-sm text-accent-900">
          <span className="font-semibold">À faire : </span>
          {finding.recommended_action}
        </p>
        {finding.has_secret && canReveal && (
          // Hors offre, le bouton reste VISIBLE et désactivé, avec l'offre qui
          // le débloque : masquer laisserait croire que le produit ne sait pas
          // le faire. La garde réelle reste côté serveur.
          <FeatureGate feature="secret_reveal">
            <Button
              variant="secondary"
              size="sm"
              icon={KeyRound}
              onClick={() => onReveal(finding.id)}
            >
              Révéler le mot de passe
            </Button>
          </FeatureGate>
        )}
      </div>

      {/* Second état du cycle de vie : la fuite reste, son mot de passe non.
          Le dire explicitement évite de laisser croire qu'il n'y en a jamais
          eu (ADR-014). */}
      {finding.secret_purged_at && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-500">
          <Trash2 className="size-3.5" aria-hidden="true" />
          Mot de passe effacé le{' '}
          {new Date(finding.secret_purged_at).toLocaleDateString('fr-FR')}, conformément à la
          politique de conservation ({retentionDays} jours).
        </p>
      )}
    </li>
  )
}

function ReuseSection({ signals }) {
  // Section dédiée en tête de la carte : la corrélation est l'information la
  // plus actionnable de l'actif, elle ne doit pas se découvrir en dépliant
  // chaque fuite une par une.
  const unique = []
  const seen = new Set()
  for (const signal of signals) {
    const key = `${signal.signal_type}:${signal.identifier}`
    if (!seen.has(key)) {
      seen.add(key)
      unique.push(signal)
    }
  }
  if (unique.length === 0) return null

  return (
    <div className="mt-3 rounded-md border border-warning-strong/30 bg-warning-subtle px-3 py-2">
      <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-warning-strong">
        <Link2 className="size-3.5" aria-hidden="true" />
        Réutilisation possible — à vérifier
      </p>
      <ul className="space-y-1">
        {unique.map((signal) => (
          <li key={`${signal.signal_type}:${signal.identifier}`} className="text-xs text-ink-700">
            <span className="font-mono">{signal.identifier}</span> — {signal.label}
            {signal.external_service && (
              <span className="text-ink-600"> ({signal.external_service})</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

function AssetCard({ group, canReveal, onReveal, expanded, onToggle, retentionDays }) {
  return (
    <Card>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full flex-wrap items-center justify-between gap-3 text-left"
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-3">
          <ExposureScoreDial
            score={group.score}
            level={group.level}
            levelLabel={group.level_label}
          />
          <div>
            <p className="text-sm font-medium text-ink-900">{group.asset_value}</p>
            <p className="text-xs text-ink-500">
              {group.asset_type_label} — {group.findings_count} élément
              {group.findings_count > 1 ? 's' : ''} à traiter
            </p>
          </div>
        </div>
        <span className="flex items-center gap-1 text-sm text-ink-500">
          {expanded ? 'Replier' : 'Voir le détail'}
          {expanded ? (
            <ChevronDown className="size-4" aria-hidden="true" />
          ) : (
            <ChevronRight className="size-4" aria-hidden="true" />
          )}
        </span>
      </button>

      {/* Garde en forme d'omission côté serveur : hors offre, le flux est
          servi sans les signaux. L'encart dit alors ce que le client ne voit
          pas — sans lui, la section disparaîtrait en silence et il ne saurait
          jamais que le produit sait rapprocher ses fuites. */}
      <ReuseSection signals={group.reuse_signals || []} />
      <div className="mt-3">
        <FeatureLockedNotice feature="reuse_correlation" />
      </div>

      {expanded && (
        <>
          <ScoreExplanation components={group.components} />
          <ul className="mt-3 space-y-3">
            {group.findings.map((finding) => (
              <FindingRow
                key={finding.id}
                finding={finding}
                canReveal={canReveal}
                onReveal={onReveal}
                retentionDays={retentionDays}
              />
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}

export default function ExposurePage() {
  const { showToast } = useToast()
  const { user, currentTenant } = useAuth()
  const isTenantAdmin = currentTenant?.role === 'admin'
  const canReveal = isTenantAdmin || Boolean(user?.is_staff)
  const canRefreshSynthesis = currentTenant?.role !== 'reader'

  const [loading, setLoading] = useState(true)
  const [feed, setFeed] = useState(null)
  const [preIncident, setPreIncident] = useState(null)
  const [showingHistory, setShowingHistory] = useState(false)
  const [expandedAssetId, setExpandedAssetId] = useState(null)
  const [revealFindingId, setRevealFindingId] = useState(null)
  const [busySignalId, setBusySignalId] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const pollRef = useRef(null)

  useEffect(() => () => clearTimeout(pollRef.current), [])

  const loadAll = useCallback(async (historyMode = false) => {
    const [feedRes, preIncidentRes] = await Promise.all([
      threatIntelligenceApi.exposureFeed(),
      threatIntelligenceApi.preIncident(historyMode ? 'treated' : undefined),
    ])
    setFeed(feedRes.data)
    setPreIncident(preIncidentRes.data)
  }, [])

  useEffect(() => {
    loadAll()
      .catch(() =>
        showToast({ type: 'error', message: 'Impossible de charger votre exposition.' })
      )
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Le premier actif est déplié d'office : en démo comme à l'usage, la page
  // doit montrer quelque chose d'actionnable sans un clic préalable.
  useEffect(() => {
    if (feed?.assets?.length && expandedAssetId === null) {
      setExpandedAssetId(feed.assets[0].asset_id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feed])

  async function handleToggleHistory() {
    const next = !showingHistory
    setShowingHistory(next)
    try {
      const response = await threatIntelligenceApi.preIncident(next ? 'treated' : undefined)
      setPreIncident(response.data)
    } catch {
      showToast({ type: 'error', message: 'Impossible de charger les signaux.' })
    }
  }

  async function handleSignalStatus(findingId, status) {
    setBusySignalId(findingId)
    try {
      await threatIntelligenceApi.updateFindingStatus(findingId, status)
      await loadAll(showingHistory)
      showToast({
        type: 'success',
        message: status === 'treated' ? 'Signal marqué traité.' : 'Signal ignoré.',
      })
    } catch {
      showToast({ type: 'error', message: 'La mise à jour n’a pas pu être enregistrée.' })
    } finally {
      setBusySignalId(null)
    }
  }

  function pollSynthesisJob(jobId) {
    async function tick() {
      try {
        const response = await aiApi.getJob(jobId)
        if (response.data.status === 'done' || response.data.status === 'failed') {
          setRefreshing(false)
          if (response.data.status === 'done') {
            await loadAll(showingHistory)
            showToast({ type: 'success', message: 'Analyse mise à jour.' })
          } else {
            showToast({ type: 'error', message: 'L’analyse n’a pas pu être générée.' })
          }
          return
        }
      } catch {
        // Hoquet réseau ponctuel — le job existe toujours côté serveur.
      }
      pollRef.current = setTimeout(tick, 2000)
    }
    tick()
  }

  async function handleRefreshSynthesis() {
    setRefreshing(true)
    try {
      const response = await threatIntelligenceApi.refreshExposureSynthesis()
      pollSynthesisJob(response.data.job_id)
    } catch (err) {
      setRefreshing(false)
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de lancer l’analyse.',
      })
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
        <h1 className="font-display text-2xl font-semibold text-ink-900">Exposition</h1>
        <p className="mt-1 text-sm text-ink-500">
          Vos actifs classés par niveau d’exposition, avec ce que chaque élément signifie et
          l’action à mener.
        </p>
      </div>

      <SynthesisBanner
        synthesis={feed?.synthesis}
        onRefresh={handleRefreshSynthesis}
        refreshing={refreshing}
        canRefresh={canRefreshSynthesis}
      />

      <PreIncidentRadar
        summary={preIncident}
        onUpdateStatus={handleSignalStatus}
        busyId={busySignalId}
        showingHistory={showingHistory}
        onToggleHistory={handleToggleHistory}
      />

      {feed?.assets?.length ? (
        <div className="space-y-4">
          {feed.assets.map((group) => (
            <AssetCard
              key={group.asset_id}
              group={group}
              canReveal={canReveal}
              onReveal={setRevealFindingId}
              expanded={expandedAssetId === group.asset_id}
              onToggle={() =>
                setExpandedAssetId(expandedAssetId === group.asset_id ? null : group.asset_id)
              }
              retentionDays={feed?.retention_policy?.secret_retention_days}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={ShieldCheck}
          title="Aucune exposition détectée"
          description="Aucune fuite ouverte sur vos actifs surveillés. Nous continuons à surveiller en permanence."
        />
      )}

      {/* La promesse de conservation limitée n'est crédible que si le client
          peut la lire dans le produit, pas seulement dans un contrat. */}
      {feed?.retention_policy && (
        <p className="flex items-start gap-2 px-1 text-xs text-ink-500">
          <Trash2 className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <span>
            Conservation : les mots de passe issus des fuites sont chiffrés et effacés
            automatiquement au bout de {feed.retention_policy.secret_retention_days} jours. La fuite
            elle-même reste dans votre historique. Le journal des révélations est conservé{' '}
            {feed.retention_policy.reveal_audit_retention_days} jours.
          </span>
        </p>
      )}

      <RevealSecretModal
        open={revealFindingId !== null}
        findingId={revealFindingId}
        onClose={() => setRevealFindingId(null)}
      />
    </div>
  )
}
