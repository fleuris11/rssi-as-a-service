import { CheckCircle2, Clock, Lock, Send, XCircle } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { accessRequestsApi } from '../api/endpoints'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card, { CardHeader } from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'
import { useEntitlements } from '../context/EntitlementsContext'

// Ce que chaque étape veut dire POUR LE CLIENT. La console parle de suivi
// commercial ; lui veut savoir si quelqu'un s'occupe de sa demande.
const ETAPES = {
  pending: {
    label: 'Reçue',
    variant: 'neutral',
    icon: Clock,
    detail: 'Votre demande est arrivée. Nous revenons vers vous.',
  },
  contacted: {
    label: 'En cours',
    variant: 'brand',
    icon: Clock,
    detail: 'Nous vous avons contacté à ce sujet.',
  },
  proposal: {
    label: 'Proposition envoyée',
    variant: 'warning',
    icon: Send,
    detail: 'Une proposition vous a été transmise.',
  },
  granted: {
    label: 'Accordée',
    variant: 'ok',
    icon: CheckCircle2,
    detail: 'C’est ouvert sur votre espace.',
  },
  declined: {
    label: 'Refusée',
    variant: 'critical',
    icon: XCircle,
    detail: '',
  },
  cancelled: {
    label: 'Annulée',
    variant: 'neutral',
    icon: XCircle,
    detail: 'Vous avez retiré cette demande.',
  },
}

function dateCourte(valeur) {
  return valeur ? new Date(valeur).toLocaleDateString('fr-FR') : '—'
}

/**
 * Où en est chaque demande, et ce qu'on peut encore demander.
 *
 * Point 8 de la consigne V2-6 : « une demande sans retour est pire que pas de
 * bouton ». C'est pour cela que l'étape est affichée en toutes lettres, avec
 * la réponse écrite quand il y en a une — et pas seulement un « en attente »
 * qui ne bouge jamais.
 */
export default function RequestsPage() {
  const { showToast } = useToast()
  const { features } = useEntitlements()
  const [demandes, setDemandes] = useState([])
  const [loading, setLoading] = useState(true)
  const [ouvert, setOuvert] = useState(null)
  const [motif, setMotif] = useState('')
  const [envoi, setEnvoi] = useState(null)
  const toastRef = useRef(showToast)
  toastRef.current = showToast

  const charger = useCallback(async () => {
    setLoading(true)
    try {
      const response = await accessRequestsApi.list()
      setDemandes(response.data)
    } catch {
      toastRef.current({ type: 'error', message: 'Impossible de charger vos demandes.' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    charger()
  }, [charger])

  const parSujet = new Map(
    demandes.filter((d) => d.is_open).map((d) => [`${d.subject_type}:${d.subject_key}`, d])
  )
  const horsOffre = (features || []).filter((f) => !f.included)

  async function handleDemander(feature) {
    setEnvoi(feature.key)
    try {
      const response = await accessRequestsApi.create({
        subject_type: 'feature',
        subject_key: feature.key,
        reason: motif,
      })
      setDemandes((prev) => [response.data, ...prev])
      setOuvert(null)
      setMotif('')
      showToast({ type: 'success', message: 'Demande envoyée. Nous revenons vers vous.' })
    } catch (err) {
      showToast({
        type: 'error',
        message: err.response?.data?.detail || 'La demande n’a pas pu être envoyée.',
      })
    } finally {
      setEnvoi(null)
    }
  }

  async function handleAnnuler(demande) {
    try {
      await accessRequestsApi.cancel(demande.id)
      await charger()
    } catch {
      showToast({ type: 'error', message: 'Impossible d’annuler cette demande.' })
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Mes demandes</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-500">
          Ce que vous avez demandé, et où en est chaque demande. Vous pouvez aussi demander ici une
          fonctionnalité qui ne fait pas partie de votre offre.
        </p>
      </div>

      <Card padding="p-0">
        <div className="p-5 pb-0">
          <CardHeader title="Vos demandes" />
        </div>
        {demandes.length === 0 ? (
          <div className="p-5 pt-0">
            <EmptyState
              icon={Send}
              title="Aucune demande"
              description="Demandez ci-dessous une fonctionnalité que votre offre ne comprend pas."
            />
          </div>
        ) : (
          <ul className="divide-y divide-ink-100 px-5 pb-3">
            {demandes.map((demande) => {
              const etape = ETAPES[demande.status] || ETAPES.pending
              const Icone = etape.icon
              return (
                <li key={demande.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink-800">{demande.subject_label}</p>
                    <p className="mt-0.5 text-xs text-ink-500">
                      {demande.subject_type_label} · demandé le {dateCourte(demande.created_at)}
                    </p>
                    {demande.reason && (
                      <p className="mt-1 max-w-2xl text-xs italic text-ink-500">
                        « {demande.reason} »
                      </p>
                    )}
                    {/* La réponse écrite, quand il y en a une. Un refus sans
                        phrase est un mur. */}
                    {demande.response && (
                      <p className="mt-1.5 max-w-2xl rounded-md bg-ink-50 px-3 py-2 text-sm text-ink-700">
                        {demande.response}
                      </p>
                    )}
                    {!demande.response && etape.detail && (
                      <p className="mt-1 text-xs text-ink-500">{etape.detail}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant={etape.variant}>
                      <Icone className="size-3" aria-hidden="true" />
                      {etape.label}
                    </Badge>
                    {demande.is_open && (
                      <Button variant="ghost" size="sm" onClick={() => handleAnnuler(demande)}>
                        Retirer
                      </Button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      <Card padding="p-0">
        <div className="p-5 pb-0">
          <CardHeader
            title="Ce que le produit sait faire de plus"
            description="Ces fonctionnalités ne sont pas comprises dans votre offre. Elles restent visibles : le produit sait les faire."
          />
        </div>
        {horsOffre.length === 0 ? (
          <div className="p-5 pt-0">
            <EmptyState
              tone="positive"
              icon={CheckCircle2}
              title="Votre offre comprend tout"
              description="Il n’y a rien de plus à demander pour le moment."
            />
          </div>
        ) : (
          <ul className="divide-y divide-ink-100 px-5 pb-3">
            {horsOffre.map((feature) => {
              const enCours = parSujet.get(`feature:${feature.key}`)
              return (
                <li key={feature.key} className="py-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 text-sm font-medium text-ink-700">
                        <Lock className="size-3.5 shrink-0 text-ink-400" aria-hidden="true" />
                        {feature.label}
                      </p>
                      <p className="mt-0.5 max-w-2xl text-xs text-ink-500">{feature.teaser}</p>
                      {feature.required_plan && (
                        <p className="mt-1 text-xs text-brand-800">
                          Comprise à partir de l’offre {feature.required_plan}.
                        </p>
                      )}
                    </div>
                    {enCours ? (
                      <Badge variant={ETAPES[enCours.status]?.variant || 'neutral'}>
                        {ETAPES[enCours.status]?.label || 'En cours'}
                      </Badge>
                    ) : (
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setOuvert(ouvert === feature.key ? null : feature.key)
                          setMotif('')
                        }}
                      >
                        Demander
                      </Button>
                    )}
                  </div>
                  {ouvert === feature.key && (
                    <div className="mt-3 rounded-md border border-ink-200 bg-canvas p-3">
                      <label className="text-xs font-medium text-ink-600" htmlFor={`motif-${feature.key}`}>
                        Pourquoi en avez-vous besoin ? (facultatif)
                      </label>
                      <textarea
                        id={`motif-${feature.key}`}
                        rows={2}
                        value={motif}
                        onChange={(event) => setMotif(event.target.value)}
                        placeholder="Ce que vous aimeriez pouvoir faire."
                        className="mt-1.5 w-full rounded-md border border-ink-200 bg-surface px-3 py-2 text-sm"
                      />
                      <div className="mt-2 flex justify-end gap-2">
                        <Button variant="ghost" onClick={() => setOuvert(null)}>
                          Annuler
                        </Button>
                        <Button
                          variant="primary"
                          icon={Send}
                          loading={envoi === feature.key}
                          onClick={() => handleDemander(feature)}
                        >
                          Envoyer la demande
                        </Button>
                      </div>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </div>
  )
}
