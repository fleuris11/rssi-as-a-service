import { BookOpen } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../../api/endpoints'
import Badge from '../../../components/ui/Badge'
import Button from '../../../components/ui/Button'
import Card, { CardHeader } from '../../../components/ui/Card'
import EmptyState from '../../../components/ui/EmptyState'
import { SkeletonCard } from '../../../components/ui/Skeleton'
import { useToast } from '../../../components/ui/Toast'

const KIND_VARIANT = { open: 'ok', licensed: 'warning', custom: 'brand' }

function dateCourte(valeur) {
  return valeur ? new Date(valeur).toLocaleDateString('fr-FR') : '—'
}

/**
 * Le catalogue de référentiels et leur attribution par client (V2-4).
 *
 * La file des demandes vivait ici en V2-4, quand un référentiel était la
 * seule chose qu'un client pouvait demander. V2-6 l'a sortie dans son propre
 * onglet : elle porte désormais aussi les demandes de fonctionnalités, et
 * c'est devenu un suivi commercial plutôt qu'un simple « accorder / refuser ».
 *
 * `kind` est affiché en évidence : c'est la question qui se pose avant
 * d'attribuer ISO 27001 ou le NIST — avons-nous le droit d'en servir le
 * contenu, et sous quelle licence (voir docs/format_import_referentiel.md).
 */
export default function ReferentialsPanel({ clients = [] }) {
  const { showToast } = useToast()
  const [catalogue, setCatalogue] = useState(null)
  const [clientChoisi, setClientChoisi] = useState('')
  const [attributions, setAttributions] = useState(null)
  const [enCours, setEnCours] = useState(null)

  const chargerCatalogue = useCallback(async () => {
    const response = await platformApi.listReferentials()
    setCatalogue(response.data)
  }, [])

  const chargerAttributions = useCallback(async (tenantId) => {
    if (!tenantId) {
      setAttributions(null)
      return
    }
    const response = await platformApi.clientReferentials(tenantId)
    setAttributions(response.data)
  }, [])

  useEffect(() => {
    chargerCatalogue()
  }, [chargerCatalogue])

  useEffect(() => {
    chargerAttributions(clientChoisi)
  }, [clientChoisi, chargerAttributions])

  async function attribuer(slug) {
    setEnCours(slug)
    try {
      const response = await platformApi.assignReferential(clientChoisi, slug)
      setAttributions(response.data)
      showToast({ type: 'success', message: 'Référentiel attribué.' })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Attribution impossible.',
      })
    } finally {
      setEnCours(null)
    }
  }

  async function retirer(slug) {
    setEnCours(slug)
    try {
      const response = await platformApi.revokeReferential(clientChoisi, slug)
      setAttributions(response.data)
      showToast({
        type: 'success',
        // On le dit à chaque retrait : c'est la question que se pose celui qui
        // clique.
        message: 'Référentiel retiré. Les diagnostics déjà produits restent consultables.',
      })
    } catch {
      showToast({ type: 'error', message: 'Retrait impossible.' })
    } finally {
      setEnCours(null)
    }
  }

  if (!catalogue) return <SkeletonCard />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Attribuer à un client"
          description="Un client ne voit que les référentiels qui lui sont attribués."
        />
        <label className="t-eyebrow" htmlFor="client-referentiels">
          Client
        </label>
        <select
          id="client-referentiels"
          className="mt-1 w-full max-w-md rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
          value={clientChoisi}
          onChange={(event) => setClientChoisi(event.target.value)}
        >
          <option value="">Choisir un client…</option>
          {clients.map((client) => (
            <option key={client.tenant_id ?? client.id} value={client.tenant_id ?? client.id}>
              {client.name}
            </option>
          ))}
        </select>

        {attributions && (
          <div className="mt-4 grid gap-6 lg:grid-cols-2">
            <div>
              <p className="t-eyebrow">Attribués</p>
              <ul className="mt-2 divide-y divide-ink-100">
                {attributions.assigned.length === 0 && (
                  <li className="py-2 text-sm text-ink-500">Aucun.</li>
                )}
                {attributions.assigned.map((ligne) => (
                  <li
                    key={ligne.slug}
                    className="flex items-center justify-between gap-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm text-ink-700">{ligne.name}</p>
                      <p className="text-xs text-ink-500">
                        {ligne.revoked_at
                          ? `Retiré le ${dateCourte(ligne.revoked_at)}${
                              ligne.readable ? ' — diagnostics conservés en lecture' : ''
                            }`
                          : `Attribué le ${dateCourte(ligne.granted_at)}`}
                      </p>
                    </div>
                    {ligne.revoked_at ? (
                      <Button
                        variant="secondary"
                        loading={enCours === ligne.slug}
                        onClick={() => attribuer(ligne.slug)}
                      >
                        Rendre l’accès
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        loading={enCours === ligne.slug}
                        onClick={() => retirer(ligne.slug)}
                      >
                        Retirer
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="t-eyebrow">Disponibles</p>
              <ul className="mt-2 divide-y divide-ink-100">
                {attributions.available.length === 0 && (
                  <li className="py-2 text-sm text-ink-500">
                    Tout le catalogue lui est déjà attribué.
                  </li>
                )}
                {attributions.available.map((ligne) => (
                  <li key={ligne.slug} className="flex items-center justify-between gap-3 py-2">
                    <span className="truncate text-sm text-ink-700">{ligne.name}</span>
                    <Button
                      variant="primary"
                      loading={enCours === ligne.slug}
                      onClick={() => attribuer(ligne.slug)}
                    >
                      Attribuer
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Catalogue"
          description="Le produit fournit la structure ; le contenu sous droits est importé par celui qui détient la licence."
        />
        {catalogue.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title="Aucun référentiel chargé"
            description="Importez-en un avec « manage.py import_referential » (voir docs/format_import_referentiel.md)."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-ink-200 text-ink-500">
                  <th className="py-2 pr-4 font-medium">Référentiel</th>
                  <th className="py-2 pr-4 font-medium">Éditeur</th>
                  <th className="py-2 pr-4 font-medium">Droits</th>
                  <th className="py-2 pr-4 text-right font-medium">Mesures</th>
                  <th className="py-2 text-right font-medium">Clients</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {catalogue.map((ref) => (
                  <tr key={ref.slug}>
                    <td className="py-2 pr-4 text-ink-800">
                      {ref.name}
                      <span className="text-ink-400"> v{ref.version}</span>
                      {ref.owner_tenant_name && (
                        <span className="text-ink-500"> — propre à {ref.owner_tenant_name}</span>
                      )}
                      {ref.licence_notice && (
                        <p className="text-xs text-ink-400">{ref.licence_notice}</p>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-ink-600">{ref.publisher || '—'}</td>
                    <td className="py-2 pr-4">
                      <Badge variant={KIND_VARIANT[ref.kind] || 'neutral'}>{ref.kind_label}</Badge>
                    </td>
                    <td className="py-2 pr-4 text-right text-ink-700">
                      {ref.measure_count > 0 ? ref.measure_count : 'à importer'}
                    </td>
                    <td className="py-2 text-right text-ink-700">{ref.assigned_tenants}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
