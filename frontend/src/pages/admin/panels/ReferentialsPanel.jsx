import { BookOpen, Check, Inbox, X } from 'lucide-react'
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
 * Le catalogue de référentiels, et la file des demandes des clients (V2-4).
 *
 * Les deux vivent sur le même écran parce qu'on y répond dans le même geste :
 * une demande arrive, on l'accorde, l'attribution est faite. Séparer les deux
 * aurait obligé l'exploitant à retrouver le client dans un autre onglet pour
 * finir ce qu'il vient de commencer.
 *
 * `kind` est affiché en évidence : c'est la question qui se pose avant
 * d'attribuer ISO 27001 ou le NIST — avons-nous le droit d'en servir le
 * contenu, et sous quelle licence (voir docs/format_import_referentiel.md).
 */
export default function ReferentialsPanel({ clients = [] }) {
  const { showToast } = useToast()
  const [catalogue, setCatalogue] = useState(null)
  const [demandes, setDemandes] = useState(null)
  const [clientChoisi, setClientChoisi] = useState('')
  const [attributions, setAttributions] = useState(null)
  const [enCours, setEnCours] = useState(null)

  const chargerCatalogue = useCallback(async () => {
    const [refs, files] = await Promise.all([
      platformApi.listReferentials(),
      platformApi.listAccessRequests(),
    ])
    setCatalogue(refs.data)
    setDemandes(files.data)
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

  async function repondre(demande, accorde) {
    setEnCours(`demande-${demande.id}`)
    try {
      const response = await platformApi.handleAccessRequest(demande.id, accorde)
      await chargerCatalogue()
      if (clientChoisi) await chargerAttributions(clientChoisi)
      showToast({
        type: 'success',
        message: response.data.granted_automatically
          ? 'Demande accordée et référentiel attribué.'
          : accorde
            ? 'Demande accordée. L’attribution reste à faire sur la fiche du client.'
            : 'Demande refusée. Le client en est informé dans son espace.',
      })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de traiter la demande.',
      })
    } finally {
      setEnCours(null)
    }
  }

  if (!catalogue || !demandes) return <SkeletonCard />

  const enAttente = demandes.results.filter((d) => d.status === 'pending')
  const traitees = demandes.results.filter((d) => d.status !== 'pending').slice(0, 10)

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Demandes des clients"
          description="Qui demande quoi, quand, et pourquoi. Accorder un référentiel l’attribue immédiatement."
          action={
            enAttente.length > 0 ? (
              <Badge variant="warning">{enAttente.length} en attente</Badge>
            ) : null
          }
        />
        {enAttente.length === 0 ? (
          <EmptyState
            tone="positive"
            icon={Inbox}
            title="Aucune demande en attente"
            description="Les demandes déposées par les clients depuis leur espace arrivent ici."
          />
        ) : (
          <ul className="divide-y divide-ink-100">
            {enAttente.map((demande) => (
              <li key={demande.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink-800">
                    {demande.tenant_name} — {demande.subject_label}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-500">
                    {demande.subject_type_label} · demandé par {demande.requested_by_email} le{' '}
                    {dateCourte(demande.created_at)}
                  </p>
                  {demande.reason && (
                    <p className="mt-1 max-w-2xl text-sm italic text-ink-600">
                      « {demande.reason} »
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="primary"
                    icon={Check}
                    loading={enCours === `demande-${demande.id}`}
                    onClick={() => repondre(demande, true)}
                  >
                    Accorder
                  </Button>
                  <Button
                    variant="secondary"
                    icon={X}
                    onClick={() => repondre(demande, false)}
                  >
                    Refuser
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {traitees.length > 0 && (
          <ul className="mt-4 space-y-1 border-t border-ink-200 pt-3 text-xs text-ink-500">
            {traitees.map((demande) => (
              <li key={demande.id}>
                {dateCourte(demande.handled_at)} — {demande.tenant_name} :{' '}
                {demande.subject_label} ({demande.status === 'granted' ? 'accordée' : 'refusée'})
              </li>
            ))}
          </ul>
        )}
      </Card>

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
