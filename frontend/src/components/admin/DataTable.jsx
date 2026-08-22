import { ArrowDown, ArrowUp, ChevronLeft, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import Button from '../ui/Button'

const PAGE_SIZE = 50

/**
 * Liste triable, filtrable et paginée.
 *
 * Le tri et la pagination sont faits côté client, à dessein : les listes de
 * ce back-office se comptent en dizaines ou en centaines de lignes, et une
 * pagination serveur ajouterait un aller-retour réseau à chaque clic de
 * colonne pour aucun gain perceptible. Le jour où une liste dépassera
 * quelques milliers de lignes, c'est l'endpoint qu'il faudra paginer — ce
 * composant garde alors la même interface.
 */
export default function DataTable({
  columns,
  rows,
  getRowKey,
  onRowClick,
  searchKeys = [],
  emptyMessage = 'Aucun élément.',
  toolbar = null,
  initialSort = null,
}) {
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState(initialSort)
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle || searchKeys.length === 0) return rows
    return rows.filter((row) =>
      searchKeys.some((key) => String(row[key] ?? '').toLowerCase().includes(needle))
    )
  }, [rows, query, searchKeys])

  const sorted = useMemo(() => {
    if (!sort) return filtered
    const { key, direction } = sort
    const factor = direction === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => {
      const left = a[key] ?? ''
      const right = b[key] ?? ''
      if (typeof left === 'number' && typeof right === 'number') return (left - right) * factor
      return String(left).localeCompare(String(right), 'fr') * factor
    })
  }, [filtered, sort])

  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  const current = Math.min(page, pageCount - 1)
  const visible = sorted.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE)

  function toggleSort(key) {
    setSort((previous) =>
      previous?.key === key
        ? { key, direction: previous.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: 'asc' }
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        {searchKeys.length > 0 && (
          <div className="relative min-w-56 flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400"
              aria-hidden="true"
            />
            <input
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                setPage(0)
              }}
              placeholder="Filtrer cette liste…"
              aria-label="Filtrer cette liste"
              className="transition-smooth w-full rounded-md border border-ink-200 py-2 pl-9 pr-3 text-sm focus-visible:outline-2 focus-visible:outline-brand-600"
            />
          </div>
        )}
        {toolbar}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-500">
              {columns.map((column) => (
                <th key={column.key} className="py-2 pr-4 font-medium">
                  {column.sortable === false ? (
                    column.label
                  ) : (
                    <button
                      type="button"
                      onClick={() => toggleSort(column.key)}
                      className="flex items-center gap-1 hover:text-ink-800"
                      aria-label={`Trier par ${column.label}`}
                    >
                      {column.label}
                      {sort?.key === column.key &&
                        (sort.direction === 'asc' ? (
                          <ArrowUp className="size-3" aria-hidden="true" />
                        ) : (
                          <ArrowDown className="size-3" aria-hidden="true" />
                        ))}
                    </button>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr
                key={getRowKey(row)}
                className={`border-b border-ink-100 last:border-0 ${
                  onRowClick ? 'cursor-pointer hover:bg-ink-50' : ''
                }`}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((column) => (
                  <td key={column.key} className="py-2.5 pr-4 text-ink-700">
                    {column.render ? column.render(row) : String(row[column.key] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {visible.length === 0 && <p className="py-6 text-center text-sm text-ink-500">{emptyMessage}</p>}

      {pageCount > 1 && (
        <div className="flex items-center justify-between text-sm text-ink-600">
          <span>
            {current * PAGE_SIZE + 1}–{Math.min((current + 1) * PAGE_SIZE, sorted.length)} sur{' '}
            {sorted.length}
          </span>
          <span className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              icon={ChevronLeft}
              disabled={current === 0}
              onClick={() => setPage(current - 1)}
            >
              Précédent
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={current >= pageCount - 1}
              onClick={() => setPage(current + 1)}
            >
              Suivant
            </Button>
          </span>
        </div>
      )}
    </div>
  )
}
