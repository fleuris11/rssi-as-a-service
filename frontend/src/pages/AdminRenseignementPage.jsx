import { useCallback, useEffect, useState } from 'react'
import { threatIntelligenceApi } from '../api/endpoints'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card, { CardHeader } from '../components/ui/Card'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'
import Defilement from '../components/ui/Defilement'

const TRIGGERED_BY_LABEL = { initial: 'Scan initial', manual: 'Scan manuel' }

function StatTile({ label, value, hint }) {
  return (
    <div className="border-t border-ink-200 pt-3">
      <p className="t-legende">{label}</p>
      <p className="n mt-1 text-2xl text-ink-900">{value}</p>
      {hint && <p className="t-meta mt-0.5">{hint}</p>}
    </div>
  )
}

export default function AdminRenseignementPage() {
  const { showToast } = useToast()
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await threatIntelligenceApi.adminStatus()
      setData(response.data)
    } catch {
      showToast({
        type: 'error',
        message: 'Impossible de charger l’état du renseignement sur la menace.',
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
      <div className="space-y-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  // `return null` laissait un ÉCRAN ENTIÈREMENT VIDE quand l'appel échouait :
  // impossible de distinguer une licence non configurée d'une panne, et rien
  // pour réessayer. Une notification passagère ne suffit pas, elle disparaît.
  if (!data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="t-display">Renseignement sur la menace</h1>
          <p className="t-meta mt-1">Vue réservée aux administrateurs plateforme.</p>
        </div>
        <div className="panneau p-6">
          <p className="t-body">
            L’état de la licence n’a pas pu être chargé. Soit aucune licence n’est configurée
            sur cet environnement, soit le service de renseignement n’a pas répondu.
          </p>
          <Button className="mt-4" onClick={load}>
            Réessayer
          </Button>
        </div>
      </div>
    )
  }

  const { quota, pool, recent_usage: recentUsage, recent_reveal_audits: recentRevealAudits } = data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="t-display">Renseignement sur la menace</h1>
        <p className="t-meta mt-1">
          Licence de renseignement partagée par toute la plateforme — vue
          réservée aux administrateurs plateforme.
        </p>
      </div>

      <Card>
        <CardHeader title="Quota mensuel de requêtes (partagé)" />
        <div className="grid gap-3 sm:grid-cols-3">
          <StatTile label="Requêtes restantes" value={quota.remaining ?? 'inconnu'} />
          <StatTile label="Consommées ce mois-ci" value={quota.monthly_requests_used} />
          <StatTile label="Marge de sécurité" value={quota.safety_margin} hint="Seuil de refus" />
        </div>
      </Card>

      <Card>
        <CardHeader title="Pool de surveillance en temps réel" />
        <div className="grid gap-3 sm:grid-cols-3">
          <StatTile label="Slots utilisés" value={pool.used} />
          <StatTile label="Capacité totale" value={pool.capacity} />
          <StatTile label="Slots libres" value={pool.remaining} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Journal d'usage récent" />
        {recentUsage.length === 0 ? (
          <p className="text-sm text-ink-500">Aucune requête enregistrée pour le moment.</p>
        ) : (
          <Defilement>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
                  <th className="py-2 pr-4 font-medium">Entreprise</th>
                  <th className="py-2 pr-4 font-medium">Déclencheur</th>
                  <th className="py-2 pr-4 font-medium">Requêtes</th>
                  <th className="py-2 pr-4 font-medium">Fuites créées</th>
                  <th className="py-2 pr-4 font-medium">Restant après</th>
                  <th className="py-2 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {recentUsage.map((row) => (
                  <tr key={row.id} className="border-b border-ink-100 last:border-0">
                    <td className="py-2 pr-4 text-ink-800">{row.tenant_name}</td>
                    <td className="py-2 pr-4 text-ink-600">
                      {TRIGGERED_BY_LABEL[row.triggered_by] || row.triggered_by}
                    </td>
                    <td className="py-2 pr-4 text-ink-600">{row.requests_consumed}</td>
                    <td className="py-2 pr-4 text-ink-600">{row.findings_created}</td>
                    <td className="py-2 pr-4 text-ink-600">{row.remaining_after ?? '—'}</td>
                    <td className="py-2 text-ink-500">
                      {new Date(row.created_at).toLocaleString('fr-FR')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Defilement>
        )}
      </Card>

      <Card>
        <CardHeader title="Journal des révélations de secrets" />
        <p className="mb-3 text-sm text-ink-500">
          Chaque tentative de révélation d’un mot de passe de fuite (accordée ou refusée), toutes
          entreprises confondues — jamais le secret lui-même.
        </p>
        {recentRevealAudits.length === 0 ? (
          <p className="text-sm text-ink-500">Aucune révélation enregistrée pour le moment.</p>
        ) : (
          <Defilement>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
                  <th className="py-2 pr-4 font-medium">Entreprise</th>
                  <th className="py-2 pr-4 font-medium">Utilisateur</th>
                  <th className="py-2 pr-4 font-medium">Fuite</th>
                  <th className="py-2 pr-4 font-medium">Résultat</th>
                  <th className="py-2 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {recentRevealAudits.map((row) => (
                  <tr key={row.id} className="border-b border-ink-100 last:border-0">
                    <td className="py-2 pr-4 text-ink-800">{row.tenant_name}</td>
                    <td className="py-2 pr-4 text-ink-600">{row.user_email || '—'}</td>
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
                ))}
              </tbody>
            </table>
          </Defilement>
        )}
      </Card>
    </div>
  )
}
