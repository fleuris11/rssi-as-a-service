import { Check, Inbox, Phone, Send, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../../api/endpoints'
import Badge from '../../../components/ui/Badge'
import Button from '../../../components/ui/Button'
import Card, { CardHeader } from '../../../components/ui/Card'
import EmptyState from '../../../components/ui/EmptyState'
import { SkeletonCard } from '../../../components/ui/Skeleton'
import { useToast } from '../../../components/ui/Toast'

// Le suivi, dans l'ordre où il se déroule. Une demande de fonctionnalité est
// une opportunité commerciale : elle se travaille avant de se conclure, et
// c'est ce que V2-4 ne savait pas dire — on n'avait qu'« accorder » ou
// « refuser », sans rien entre les deux.
const COLONNES = [
  { status: 'pending', label: 'Nouvelles', variant: 'neutral' },
  { status: 'contacted', label: 'Contactés', variant: 'brand' },
  { status: 'proposal', label: 'Proposition', variant: 'warning' },
]

const ACTIONS = [
  { status: 'contacted', label: 'Contacté', icon: Phone, variant: 'secondary' },
  { status: 'proposal', label: 'Proposition envoyée', icon: Send, variant: 'secondary' },
  { status: 'granted', label: 'Accorder', icon: Check, variant: 'primary' },
  { status: 'declined', label: 'Refuser', icon: X, variant: 'secondary' },
]

const ETAPE_VARIANT = {
  pending: 'neutral',
  contacted: 'brand',
  proposal: 'warning',
  granted: 'ok',
  declined: 'critical',
  cancelled: 'neutral',
}

function dateCourte(valeur) {
  return valeur ? new Date(valeur).toLocaleDateString('fr-FR') : '—'
}

/**
 * La file des demandes des clients, devenue un suivi (V2-6).
 *
 * Sortie de `ReferentialsPanel` : elle ne concerne plus les seuls
 * référentiels. Un client peut demander une fonctionnalité, et demain autre
 * chose — le mécanisme est générique depuis V2-4, l'écran devait le devenir.
 */
export default function RequestsPanel() {
  const { showToast } = useToast()
  const [file, setFile] = useState(null)
  const [enCours, setEnCours] = useState(null)
  const [reponseOuverte, setReponseOuverte] = useState(null)
  const [reponse, setReponse] = useState('')

  const charger = useCallback(async () => {
    const response = await platformApi.listAccessRequests()
    setFile(response.data)
  }, [])

  useEffect(() => {
    charger()
  }, [charger])

  async function avancer(demande, status) {
    setEnCours(`${demande.id}-${status}`)
    try {
      const response = await platformApi.advanceAccessRequest(demande.id, status, reponse)
      await charger()
      setReponseOuverte(null)
      setReponse('')
      showToast({
        type: 'success',
        message:
          status === 'granted'
            ? response.data.granted_automatically
              ? 'Demande accordée et attribuée.'
              : 'Demande accordée. L’attribution reste à faire sur la fiche du client.'
            : 'Suivi mis à jour. Le client le voit depuis son espace.',
      })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'Impossible de mettre à jour cette demande.',
      })
    } finally {
      setEnCours(null)
    }
  }

  if (!file) return <SkeletonCard />

  const ouvertes = file.results.filter((d) => d.is_open)
  const conclues = file.results.filter((d) => !d.is_open).slice(0, 12)

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Demandes des clients"
          description="Qui demande quoi, quand, et pourquoi. Chaque étape est visible par le client depuis son espace."
          action={
            file.open_count > 0 ? (
              <Badge variant="warning">{file.open_count} en cours</Badge>
            ) : null
          }
        />
        <div className="mb-4 flex flex-wrap gap-4 border-b border-ink-100 pb-3">
          {COLONNES.map((colonne) => (
            <div key={colonne.status}>
              <p className="t-eyebrow">{colonne.label}</p>
              <p className="font-display text-xl font-semibold text-ink-900">
                {ouvertes.filter((d) => d.status === colonne.status).length}
              </p>
            </div>
          ))}
        </div>

        {ouvertes.length === 0 ? (
          <EmptyState
            tone="positive"
            icon={Inbox}
            title="Aucune demande en cours"
            description="Les demandes déposées par les clients depuis leur espace arrivent ici."
          />
        ) : (
          <ul className="divide-y divide-ink-100">
            {ouvertes.map((demande) => (
              <li key={demande.id} className="py-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
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
                  <Badge variant={ETAPE_VARIANT[demande.status]}>{demande.status_label}</Badge>
                </div>

                <div className="mt-2.5 flex flex-wrap gap-2">
                  {ACTIONS.filter((action) => action.status !== demande.status).map((action) => (
                    <Button
                      key={action.status}
                      variant={action.variant}
                      size="sm"
                      icon={action.icon}
                      loading={enCours === `${demande.id}-${action.status}`}
                      onClick={() => {
                        // Accorder ou refuser mérite une phrase : c'est ce
                        // que le client lira dans son espace. Les étapes
                        // intermédiaires, elles, se posent d'un clic.
                        if (action.status === 'granted' || action.status === 'declined') {
                          setReponseOuverte(`${demande.id}-${action.status}`)
                          setReponse('')
                        } else {
                          avancer(demande, action.status)
                        }
                      }}
                    >
                      {action.label}
                    </Button>
                  ))}
                </div>

                {(reponseOuverte === `${demande.id}-granted` ||
                  reponseOuverte === `${demande.id}-declined`) && (
                  <div className="mt-2.5 rounded-md border border-ink-200 bg-canvas p-3">
                    <label className="text-xs font-medium text-ink-600" htmlFor={`rep-${demande.id}`}>
                      Ce que le client lira
                    </label>
                    <textarea
                      id={`rep-${demande.id}`}
                      rows={2}
                      value={reponse}
                      onChange={(event) => setReponse(event.target.value)}
                      placeholder="Une phrase suffit. Un refus sans explication est un mur."
                      className="mt-1.5 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
                    />
                    <div className="mt-2 flex justify-end gap-2">
                      <Button variant="ghost" size="sm" onClick={() => setReponseOuverte(null)}>
                        Annuler
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() =>
                          avancer(demande, reponseOuverte.endsWith('granted') ? 'granted' : 'declined')
                        }
                      >
                        Confirmer
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {conclues.length > 0 && (
        <Card>
          <CardHeader title="Demandes conclues" />
          <ul className="space-y-1 text-xs text-ink-500">
            {conclues.map((demande) => (
              <li key={demande.id}>
                {dateCourte(demande.handled_at)} — {demande.tenant_name} : {demande.subject_label} (
                {demande.status_label})
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
