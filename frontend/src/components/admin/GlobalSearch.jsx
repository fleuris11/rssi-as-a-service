import { Search, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { platformApi } from '../../api/endpoints'

/**
 * Une seule barre pour retrouver une entreprise, une personne ou un prospect.
 *
 * Recherche différée de 250 ms : taper « Menuiserie » enverrait sinon dix
 * requêtes pour un seul besoin. Sous deux caractères, le serveur ne répond
 * rien — inutile de l'appeler.
 */
export default function GlobalSearch({ onSelectTenant, onSelectProspect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const timer = useRef(null)

  useEffect(() => {
    clearTimeout(timer.current)
    if (query.trim().length < 2) {
      setResults(null)
      return
    }
    timer.current = setTimeout(async () => {
      try {
        const response = await platformApi.search(query)
        setResults(response.data)
      } catch {
        setResults(null)
      }
    }, 250)
    return () => clearTimeout(timer.current)
  }, [query])

  const total =
    (results?.tenants.length || 0) +
    (results?.users.length || 0) +
    (results?.prospects.length || 0)

  function pick(action) {
    setQuery('')
    setResults(null)
    action()
  }

  return (
    <div className="relative">
      <Search
        className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-300"
        aria-hidden="true"
      />
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Rechercher une entreprise, une personne, un prospect…"
        aria-label="Recherche globale"
        className="w-full rounded-md border border-brand-700 bg-brand-800 py-1.5 pl-9 pr-8 text-sm text-white placeholder:text-brand-300 focus-visible:outline-2 focus-visible:outline-white"
      />
      {query && (
        <button
          type="button"
          onClick={() => setQuery('')}
          aria-label="Effacer la recherche"
          className="absolute right-2 top-1/2 -translate-y-1/2 text-brand-300 hover:text-white"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      )}

      {results && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-96 overflow-y-auto rounded-md border border-ink-200 bg-white py-2 shadow-lg">
          {total === 0 && (
            <p className="px-3 py-2 text-sm text-ink-500">Aucun résultat pour « {results.query} ».</p>
          )}

          {results.tenants.length > 0 && (
            <>
              <p className="px-3 py-1 text-xs font-semibold uppercase tracking-wide text-ink-400">
                Entreprises
              </p>
              {results.tenants.map((tenant) => (
                <button
                  key={tenant.id}
                  type="button"
                  onClick={() => pick(() => onSelectTenant(tenant.id))}
                  className="block w-full px-3 py-1.5 text-left text-sm text-ink-800 hover:bg-ink-50"
                >
                  {tenant.name}
                  {tenant.plan_name && <span className="text-ink-500"> — {tenant.plan_name}</span>}
                  {tenant.archived && <span className="text-ink-400"> (archivée)</span>}
                </button>
              ))}
            </>
          )}

          {results.users.length > 0 && (
            <>
              <p className="mt-1 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-ink-400">
                Personnes
              </p>
              {results.users.map((user) => (
                <button
                  key={user.id}
                  type="button"
                  disabled={!user.tenant_id}
                  onClick={() => pick(() => onSelectTenant(user.tenant_id))}
                  className="block w-full px-3 py-1.5 text-left text-sm text-ink-800 hover:bg-ink-50 disabled:text-ink-400"
                >
                  {user.email}
                  {user.tenant_name && <span className="text-ink-500"> — {user.tenant_name}</span>}
                  {user.is_staff && <span className="text-ink-400"> (administrateur)</span>}
                  {!user.is_active && <span className="text-ink-400"> · inactif</span>}
                </button>
              ))}
            </>
          )}

          {results.prospects.length > 0 && (
            <>
              <p className="mt-1 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-ink-400">
                Prospects
              </p>
              {results.prospects.map((prospect) => (
                <button
                  key={prospect.id}
                  type="button"
                  onClick={() => pick(() => onSelectProspect(prospect.id))}
                  className="block w-full px-3 py-1.5 text-left text-sm text-ink-800 hover:bg-ink-50"
                >
                  {prospect.company} — {prospect.full_name}
                  <span className="text-ink-500"> · {prospect.status_label}</span>
                </button>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
