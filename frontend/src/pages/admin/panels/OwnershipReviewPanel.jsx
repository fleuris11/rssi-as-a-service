import { AlertTriangle, ShieldQuestion } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../../api/endpoints'
import Badge from '../../../components/ui/Badge'
import Card, { CardHeader } from '../../../components/ui/Card'
import EmptyState from '../../../components/ui/EmptyState'
import { SkeletonCard } from '../../../components/ui/Skeleton'

/**
 * Les actifs dont la possession n'est pas établie (ADR-026).
 *
 * Ce sont ceux déclarés AVANT la V2-1 : ni preuve, ni déclaration tracée,
 * parce que ni l'une ni l'autre n'existaient. Ils continuent d'être
 * surveillés — couper un client pour une règle postérieure à son engagement
 * serait le punir de notre propre retard — mais l'exploitant doit savoir ce
 * qui reste à régulariser, et avec qui en parler.
 *
 * C'est l'écran qui aurait montré `ratp.fr`, déclaré par un client qui ne le
 * possède pas, sans qu'il faille lire la base pour s'en apercevoir.
 */
export default function OwnershipReviewPanel() {
  const [data, setData] = useState(null)

  const load = useCallback(async () => {
    const response = await platformApi.ownershipReview()
    setData(response.data)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (!data) return <SkeletonCard />

  if (data.count === 0) {
    return (
      <EmptyState
        tone="positive"
        icon={ShieldQuestion}
        title="Rien à régulariser"
        description="Tous les actifs déclarés portent soit une preuve de possession, soit une déclaration sur l’honneur tracée."
      />
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Actifs à régulariser"
          subtitle="Déclarés avant l’exigence de preuve. Ils restent surveillés — rien n’est coupé."
        />
        <div className="flex flex-wrap gap-6 px-1 pt-2">
          <div>
            <p className="t-eyebrow">À régulariser</p>
            <p className="font-display text-2xl font-semibold text-ink-900">{data.count}</p>
          </div>
          <div>
            <p className="t-eyebrow">Dont en surveillance continue</p>
            {/* Le sous-ensemble urgent : ceux-là occupent un emplacement de la
                licence et font parvenir des alertes sur un domaine qui n'est
                peut-être pas celui du client. */}
            <p
              className={`font-display text-2xl font-semibold ${
                data.under_continuous_monitoring > 0 ? 'text-critical-strong' : 'text-ink-900'
              }`}
            >
              {data.under_continuous_monitoring}
            </p>
          </div>
        </div>
      </Card>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead>
              <tr className="border-b border-ink-100 text-left">
                <th className="t-eyebrow py-2">Client</th>
                <th className="t-eyebrow py-2">Actif</th>
                <th className="t-eyebrow py-2">Domaine</th>
                <th className="t-eyebrow py-2">Déclaré le</th>
                <th className="t-eyebrow py-2">État</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((ligne) => (
                <tr key={ligne.asset_id} className="border-b border-ink-50 last:border-0">
                  <td className="py-2 pr-4 text-ink-800">{ligne.tenant_name}</td>
                  <td className="py-2 pr-4 text-ink-600">{ligne.asset_value}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-ink-600">{ligne.domain}</td>
                  <td className="py-2 pr-4 text-ink-500">
                    {new Date(ligne.declared_at).toLocaleDateString('fr-FR')}
                  </td>
                  <td className="py-2">
                    {ligne.under_continuous_monitoring ? (
                      <Badge variant="critical">
                        <AlertTriangle className="mr-1 inline size-3" aria-hidden="true" />
                        Surveillance continue
                      </Badge>
                    ) : (
                      <Badge variant="warning">À vérifier</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
