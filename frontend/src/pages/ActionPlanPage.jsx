import { useCallback, useEffect, useMemo, useState } from 'react'
import { actionsApi, tenantsApi } from '../api/endpoints'

const STATUSES = [
  { value: 'todo', label: 'À faire' },
  { value: 'in_progress', label: 'En cours' },
  { value: 'done', label: 'Fait' },
]

const NEXT_STATUS = { todo: 'in_progress', in_progress: 'done' }
const PREVIOUS_STATUS = { in_progress: 'todo', done: 'in_progress' }

function formatScore(score) {
  return score === null || score === undefined ? 'Non évalué' : `${score}/100`
}

export default function ActionPlanPage() {
  const [items, setItems] = useState([])
  const [members, setMembers] = useState([])
  const [projected, setProjected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [updatingId, setUpdatingId] = useState(null)

  const refreshProjectedScore = useCallback(async () => {
    try {
      const response = await actionsApi.projectedScore()
      setProjected(response.data)
    } catch {
      setProjected(null)
    }
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [itemsList, membersRes] = await Promise.all([
        actionsApi.listAll(),
        tenantsApi.listMembers(),
      ])
      setItems(itemsList)
      setMembers(membersRes.data.results)
      await refreshProjectedScore()
    } catch {
      setError("Impossible de charger le plan d'action.")
    } finally {
      setLoading(false)
    }
  }, [refreshProjectedScore])

  useEffect(() => {
    load()
  }, [load])

  const columns = useMemo(() => {
    const grouped = { todo: [], in_progress: [], done: [] }
    for (const item of items) {
      grouped[item.status]?.push(item)
    }
    return grouped
  }, [items])

  async function updateItem(id, payload) {
    setUpdatingId(id)
    setError('')
    try {
      const response = await actionsApi.update(id, payload)
      setItems((prev) => prev.map((item) => (item.id === id ? response.data : item)))
      if ('status' in payload) {
        await refreshProjectedScore()
      }
    } catch {
      setError("La mise à jour n'a pas pu être enregistrée.")
    } finally {
      setUpdatingId(null)
    }
  }

  if (loading) {
    return <p className="text-slate-500">Chargement du plan d’action…</p>
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Plan d’action</h1>
        <p className="mt-1 text-sm text-slate-500">
          Priorisé par ratio impact/effort — les actions rapides à fort impact en premier.
        </p>
      </div>

      {projected && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-500">
            Score projeté une fois le plan terminé
          </p>
          <p className="mt-1 text-3xl font-semibold text-slate-900">
            {formatScore(projected.global_score)}
          </p>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {items.length === 0 ? (
        <p className="text-slate-600">
          Aucune action en attente — terminez une évaluation pour générer votre plan d’action.
        </p>
      ) : (
        <div className="grid gap-6 md:grid-cols-3">
          {STATUSES.map((column) => (
            <div
              key={column.value}
              className="rounded-lg border border-slate-200 bg-slate-100 p-4"
            >
              <h2 className="text-sm font-semibold text-slate-700">
                {column.label} ({columns[column.value].length})
              </h2>
              <ul className="mt-3 space-y-3">
                {columns[column.value].map((item) => (
                  <li
                    key={item.id}
                    className="rounded-md border border-slate-200 bg-white p-3 shadow-sm"
                  >
                    <p className="text-sm font-medium text-slate-800">
                      {item.measure.official_title}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-400">{item.domain_name}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                      <span className="rounded bg-slate-100 px-1.5 py-0.5">
                        Priorité {item.priority}
                      </span>
                      <span className="rounded bg-slate-100 px-1.5 py-0.5">
                        Impact {item.measure.impact}
                      </span>
                      <span className="rounded bg-slate-100 px-1.5 py-0.5">
                        Effort {item.measure.effort}
                      </span>
                    </div>

                    <label className="mt-3 block text-xs text-slate-500">
                      Assigné à
                      <select
                        value={item.assignee ?? ''}
                        disabled={updatingId === item.id}
                        onChange={(e) => updateItem(item.id, { assignee: e.target.value || null })}
                        className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700"
                      >
                        <option value="">Non assigné</option>
                        {members.map((member) => (
                          <option key={member.user_id} value={member.user_id}>
                            {member.email}
                          </option>
                        ))}
                      </select>
                    </label>

                    <div className="mt-3 flex gap-2">
                      {PREVIOUS_STATUS[item.status] && (
                        <button
                          type="button"
                          disabled={updatingId === item.id}
                          onClick={() =>
                            updateItem(item.id, { status: PREVIOUS_STATUS[item.status] })
                          }
                          className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:border-slate-400 disabled:opacity-50"
                        >
                          ← Reculer
                        </button>
                      )}
                      {NEXT_STATUS[item.status] && (
                        <button
                          type="button"
                          disabled={updatingId === item.id}
                          onClick={() =>
                            updateItem(item.id, { status: NEXT_STATUS[item.status] })
                          }
                          className="rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                        >
                          {item.status === 'todo' ? 'Commencer →' : 'Marquer fait →'}
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
