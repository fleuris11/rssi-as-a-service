import { Bell } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { notificationsApi } from '../api/endpoints'
import { ProfileDate } from './DisplayProfile'

/**
 * La cloche (lot C, point 20 ; ADR-037).
 *
 * Le compteur est interrogé toutes les minutes, et SEULEMENT quand l'onglet
 * est visible : une cloche qui interroge le serveur dans cinquante onglets
 * oubliés consomme pour rien (exigence de sobriété). La liste, plus lourde,
 * n'est chargée qu'à l'ouverture.
 */

export const INTERVALLE_MS = 60_000
const DERNIERES = 8

export default function NotificationBell() {
  const navigate = useNavigate()
  const [nonLues, setNonLues] = useState(0)
  const [ouvert, setOuvert] = useState(false)
  const [liste, setListe] = useState(null)
  const panneauRef = useRef(null)

  const compter = useCallback(async () => {
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
    try {
      const reponse = await notificationsApi.unreadCount()
      setNonLues(reponse.data.unread)
    } catch {
      // Une cloche muette vaut mieux qu'une erreur sur chaque écran.
    }
  }, [])

  useEffect(() => {
    compter()
    const minuterie = setInterval(compter, INTERVALLE_MS)
    document.addEventListener('visibilitychange', compter)
    return () => {
      clearInterval(minuterie)
      document.removeEventListener('visibilitychange', compter)
    }
  }, [compter])

  useEffect(() => {
    if (!ouvert) return undefined
    function fermer(event) {
      if (event.key === 'Escape') setOuvert(false)
    }
    function dehors(event) {
      if (panneauRef.current && !panneauRef.current.contains(event.target)) setOuvert(false)
    }
    document.addEventListener('keydown', fermer)
    document.addEventListener('mousedown', dehors)
    return () => {
      document.removeEventListener('keydown', fermer)
      document.removeEventListener('mousedown', dehors)
    }
  }, [ouvert])

  async function basculer() {
    const suivant = !ouvert
    setOuvert(suivant)
    if (suivant) {
      try {
        const reponse = await notificationsApi.inbox({ page_size: DERNIERES })
        setListe(reponse.data.results.slice(0, DERNIERES))
      } catch {
        setListe([])
      }
    }
  }

  async function ouvrir(notification) {
    setOuvert(false)
    if (!notification.is_read) {
      try {
        await notificationsApi.markRead([notification.id])
        setNonLues((n) => Math.max(0, n - 1))
      } catch {
        // La navigation ne dépend pas du marquage.
      }
    }
    if (notification.link) navigate(notification.link)
  }

  async function toutLire() {
    try {
      await notificationsApi.markAllRead()
      setNonLues(0)
      setListe((l) => (l || []).map((n) => ({ ...n, is_read: true })))
    } catch {
      // Sans effet visible : le compteur se resynchronise à la minute suivante.
    }
  }

  return (
    <div className="relative" ref={panneauRef}>
      <button
        type="button"
        onClick={basculer}
        aria-expanded={ouvert}
        aria-haspopup="true"
        aria-label={
          nonLues > 0
            ? `Notifications, ${nonLues} non lue${nonLues > 1 ? 's' : ''}`
            : 'Notifications, aucune non lue'
        }
        className="transition-smooth relative rounded-md p-1.5 text-ink-600 hover:bg-ink-100 focus-visible:outline-2 focus-visible:outline-brand-600"
      >
        <Bell className="size-5" aria-hidden="true" />
        {nonLues > 0 && (
          <span
            aria-hidden="true"
            className="absolute -right-0.5 -top-0.5 flex min-w-4 items-center justify-center rounded-full bg-critical-strong px-1 text-[10px] font-semibold leading-4 text-white"
          >
            {nonLues > 99 ? '99+' : nonLues}
          </span>
        )}
      </button>

      {ouvert && (
        <div
          role="region"
          aria-label="Dernières notifications"
          className="absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-ink-200 bg-surface shadow-elevated"
        >
          <div className="flex items-center justify-between gap-2 border-b border-ink-100 px-3 py-2">
            <p className="text-sm font-semibold text-ink-800">Notifications</p>
            {nonLues > 0 && (
              <button
                type="button"
                onClick={toutLire}
                className="text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                Tout marquer comme lu
              </button>
            )}
          </div>
          {liste === null ? (
            <p className="px-3 py-4 text-sm text-ink-500">Chargement…</p>
          ) : liste.length === 0 ? (
            <p className="px-3 py-4 text-sm text-ink-500">Rien de nouveau pour le moment.</p>
          ) : (
            <ul className="max-h-96 divide-y divide-ink-100 overflow-y-auto">
              {liste.map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => ouvrir(notification)}
                    className={`transition-smooth block w-full px-3 py-2.5 text-left hover:bg-ink-50 ${
                      notification.is_read ? '' : 'bg-brand-50/60'
                    }`}
                  >
                    <span className="flex items-start gap-2">
                      {!notification.is_read && (
                        <span className="mt-1.5 size-2 shrink-0 rounded-full bg-brand-600" aria-hidden="true" />
                      )}
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-ink-800">
                          {notification.title}
                          {!notification.is_read && <span className="sr-only"> (non lue)</span>}
                        </span>
                        <span className="mt-0.5 block text-xs text-ink-500">
                          {notification.tenant_name ? `${notification.tenant_name} · ` : ''}
                          <ProfileDate value={notification.created_at} />
                        </span>
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-ink-100 px-3 py-2">
            <Link
              to="/notifications"
              onClick={() => setOuvert(false)}
              className="text-sm font-medium text-brand-600 hover:text-brand-700"
            >
              Voir toutes les notifications
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
