import { Bell, Search } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { notificationsApi } from '../api/endpoints'
import { ProfileDate } from '../components/DisplayProfile'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

/**
 * Toutes les notifications (lot C, point 20). Filtre « non lues », recherche
 * dans le titre et le texte (point 22 : tout ce qui dépasse vingt lignes se
 * cherche), pagination servie par le serveur.
 */
export default function NotificationsPage() {
  const { showToast } = useToast()
  const navigate = useNavigate()
  const [filtre, setFiltre] = useState('toutes')
  const [recherche, setRecherche] = useState('')
  const [requete, setRequete] = useState('')
  const [page, setPage] = useState(1)
  const [donnees, setDonnees] = useState(null)

  // La recherche part après une courte pause de frappe : une requête par
  // lettre saisie ne sert personne.
  useEffect(() => {
    const minuterie = setTimeout(() => {
      setRequete(recherche.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(minuterie)
  }, [recherche])

  const charger = useCallback(async () => {
    try {
      const params = { page }
      if (filtre === 'non-lues') params.unread = '1'
      if (requete) params.q = requete
      const reponse = await notificationsApi.inbox(params)
      setDonnees(reponse.data)
    } catch {
      showToast({ type: 'error', message: 'Impossible de charger les notifications.' })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtre, requete, page])

  useEffect(() => {
    charger()
  }, [charger])

  async function ouvrir(notification) {
    if (!notification.is_read) {
      try {
        await notificationsApi.markRead([notification.id])
      } catch {
        // La navigation ne dépend pas du marquage.
      }
    }
    if (notification.link) navigate(notification.link)
    else charger()
  }

  async function toutLire() {
    try {
      const reponse = await notificationsApi.markAllRead()
      showToast({ type: 'success', message: `${reponse.data.updated} notification(s) marquée(s) comme lue(s).` })
      charger()
    } catch {
      showToast({ type: 'error', message: 'Le marquage n’a pas pu être enregistré.' })
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-900">Notifications</h1>
          <p className="mt-1 text-sm text-ink-500">
            Ce qui s’est passé et qui vous concerne : demandes, fuites détectées, rapports, veille.
          </p>
        </div>
        <Button variant="secondary" onClick={toutLire}>
          Tout marquer comme lu
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1" role="group" aria-label="Filtrer les notifications">
          {[
            ['toutes', 'Toutes'],
            ['non-lues', 'Non lues'],
          ].map(([cle, libelle]) => (
            <button
              key={cle}
              type="button"
              aria-pressed={filtre === cle}
              onClick={() => {
                setFiltre(cle)
                setPage(1)
              }}
              className={`transition-smooth rounded-md px-3 py-1.5 text-sm font-medium ${
                filtre === cle ? 'bg-brand-600 text-white' : 'bg-ink-50 text-ink-600 hover:bg-ink-100'
              }`}
            >
              {libelle}
            </button>
          ))}
        </div>
        <label className="relative min-w-0 flex-1 sm:max-w-xs">
          <span className="sr-only">Rechercher dans les notifications</span>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-500" aria-hidden="true" />
          <input
            type="search"
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
            placeholder="Rechercher…"
            className="w-full rounded-md border border-ink-200 py-1.5 pl-8 pr-3 text-sm focus-visible:outline-2 focus-visible:outline-brand-600"
          />
        </label>
      </div>

      {donnees === null ? (
        <SkeletonCard />
      ) : donnees.results.length === 0 ? (
        <EmptyState
          icon={Bell}
          title={requete || filtre === 'non-lues' ? 'Aucune notification ne correspond' : 'Aucune notification'}
          description="Vous serez prévenu ici dès qu’un événement vous concerne."
        />
      ) : (
        <Card padding="p-0">
          <ul className="divide-y divide-ink-100">
            {donnees.results.map((notification) => (
              <li key={notification.id}>
                <button
                  type="button"
                  onClick={() => ouvrir(notification)}
                  className={`transition-smooth block w-full px-4 py-3 text-left hover:bg-ink-50 ${
                    notification.is_read ? '' : 'bg-brand-50/60'
                  }`}
                >
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-ink-800">{notification.title}</span>
                    {!notification.is_read && <Badge variant="brand">Non lue</Badge>}
                  </span>
                  {notification.body && (
                    <span className="mt-0.5 block text-sm text-ink-600">{notification.body}</span>
                  )}
                  <span className="mt-1 block text-xs text-ink-500">
                    {notification.kind_label}
                    {notification.tenant_name ? ` · ${notification.tenant_name}` : ''} ·{' '}
                    <ProfileDate value={notification.created_at} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {donnees && (donnees.previous || donnees.next) && (
        <div className="flex items-center justify-between text-sm">
          <p className="text-ink-500">
            {donnees.count} notification(s) — page {page}
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={!donnees.previous} onClick={() => setPage((p) => p - 1)}>
              Précédente
            </Button>
            <Button variant="secondary" size="sm" disabled={!donnees.next} onClick={() => setPage((p) => p + 1)}>
              Suivante
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
