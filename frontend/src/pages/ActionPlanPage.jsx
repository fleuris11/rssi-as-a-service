import { Zap } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { actionsApi, tenantsApi } from '../api/endpoints'
import Badge from '../components/ui/Badge'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import { SkeletonCard } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'

const STATUSES = [
  { value: 'todo', label: 'À faire' },
  { value: 'in_progress', label: 'En cours' },
  { value: 'done', label: 'Fait' },
]

const NEXT_STATUS = { todo: 'in_progress', in_progress: 'done' }
const PREVIOUS_STATUS = { in_progress: 'todo', done: 'in_progress' }

const LEVEL_LABEL = { low: 'Faible', medium: 'Moyen', high: 'Élevé' }

function formatScore(score) {
  return score === null || score === undefined ? 'Non évalué' : `${score}/100`
}

function isQuickWin(item) {
  return item.measure.impact === 'high' && item.measure.effort === 'low'
}

function AssigneeAvatar({ email }) {
  const initials = email ? email.slice(0, 2).toUpperCase() : '—'
  return (
    <div
      className="flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[10px] font-semibold text-brand-700"
      title={email || 'Non assigné'}
    >
      {initials}
    </div>
  )
}

function ActionCard({ item, members, updatingId, onUpdate }) {
  return (
    <Card padding="p-3" className="space-y-2.5">
      <div className="flex flex-wrap items-center gap-1.5">
        {isQuickWin(item) && (
          <Badge variant="accent">
            <Zap className="size-3" aria-hidden="true" />
            Quick win
          </Badge>
        )}
        <Badge variant="brand">Priorité {item.priority}</Badge>
      </div>

      <div>
        <p className="text-sm font-medium text-ink-800">{item.measure.official_title}</p>
        <p className="mt-0.5 text-xs text-ink-500">{item.domain_name}</p>
      </div>

      <div className="flex flex-wrap gap-1.5 text-xs text-ink-600">
        <span className="rounded bg-ink-100 px-1.5 py-0.5">
          Impact {LEVEL_LABEL[item.measure.impact]}
        </span>
        <span className="rounded bg-ink-100 px-1.5 py-0.5">
          Effort {LEVEL_LABEL[item.measure.effort]}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <AssigneeAvatar email={item.assignee_email} />
        <select
          aria-label="Assigné à"
          value={item.assignee ?? ''}
          disabled={updatingId === item.id}
          onChange={(e) => onUpdate(item.id, { assignee: e.target.value || null })}
          className="transition-smooth min-w-0 flex-1 rounded-md border border-ink-200 px-2 py-1 text-xs text-ink-700 focus-visible:outline-2 focus-visible:outline-brand-600"
        >
          <option value="">Non assigné</option>
          {members.map((member) => (
            <option key={member.user_id} value={member.user_id}>
              {member.email}
            </option>
          ))}
        </select>
      </div>

      <div className="flex gap-2 pt-0.5">
        {PREVIOUS_STATUS[item.status] && (
          <button
            type="button"
            disabled={updatingId === item.id}
            onClick={() => onUpdate(item.id, { status: PREVIOUS_STATUS[item.status] })}
            className="transition-smooth rounded-md border border-ink-200 px-2 py-1 text-xs text-ink-600 hover:border-ink-300 disabled:opacity-50"
          >
            ← Reculer
          </button>
        )}
        {NEXT_STATUS[item.status] && (
          <button
            type="button"
            disabled={updatingId === item.id}
            onClick={() => onUpdate(item.id, { status: NEXT_STATUS[item.status] })}
            className="transition-smooth rounded-md bg-brand-700 px-2 py-1 text-xs font-medium text-white hover:bg-brand-800 disabled:opacity-50"
          >
            {item.status === 'todo' ? 'Commencer →' : 'Marquer fait →'}
          </button>
        )}
      </div>
    </Card>
  )
}

export default function ActionPlanPage() {
  const { showToast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const domainFilter = searchParams.get('domaine') || ''
  const [items, setItems] = useState([])
  const [members, setMembers] = useState([])
  const [projected, setProjected] = useState(null)
  const [loading, setLoading] = useState(true)
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
    try {
      const [itemsList, membersRes] = await Promise.all([
        actionsApi.listAll(),
        tenantsApi.listMembers(),
      ])
      setItems(itemsList)
      setMembers(membersRes.data.results)
      await refreshProjectedScore()
    } catch {
      showToast({
        type: 'error',
        message: 'Impossible de charger le plan d’action.',
        action: { label: 'Réessayer', onClick: load },
      })
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshProjectedScore])

  useEffect(() => {
    load()
  }, [load])

  const domains = useMemo(
    () => [...new Set(items.map((item) => item.domain_name))].sort(),
    [items]
  )

  const filteredItems = useMemo(
    () => (domainFilter ? items.filter((item) => item.domain_name === domainFilter) : items),
    [items, domainFilter]
  )

  const columns = useMemo(() => {
    const grouped = { todo: [], in_progress: [], done: [] }
    for (const item of filteredItems) {
      grouped[item.status]?.push(item)
    }
    return grouped
  }, [filteredItems])

  async function updateItem(id, payload) {
    setUpdatingId(id)
    try {
      const response = await actionsApi.update(id, payload)
      setItems((prev) => prev.map((item) => (item.id === id ? response.data : item)))
      if ('status' in payload) {
        await refreshProjectedScore()
      }
    } catch {
      showToast({ type: 'error', message: 'La mise à jour n’a pas pu être enregistrée.' })
    } finally {
      setUpdatingId(null)
    }
  }

  if (loading) {
    return (
      <div className="grid gap-6 md:grid-cols-3">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink-900">Plan d’action</h1>
          <p className="mt-1 text-sm text-ink-500">
            Priorisé par ratio impact/effort — les actions rapides à fort impact en premier.
          </p>
        </div>
        {domains.length > 0 && (
          <label className="text-sm text-ink-600">
            <span className="mr-2">Domaine</span>
            <select
              value={domainFilter}
              onChange={(e) => {
                const value = e.target.value
                setSearchParams(value ? { domaine: value } : {})
              }}
              className="transition-smooth rounded-md border border-ink-200 px-3 py-1.5 text-sm text-ink-700 focus-visible:outline-2 focus-visible:outline-brand-600"
            >
              <option value="">Tous les domaines</option>
              {domains.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {projected && (
        <Card>
          <p className="text-sm font-medium text-ink-500">Score projeté une fois le plan terminé</p>
          <p className="mt-1 font-display text-3xl font-semibold text-ink-900">
            {formatScore(projected.global_score)}
          </p>
        </Card>
      )}

      {/* Deux vides très différents, et un seul message les couvrait.
          Un client qui venait de terminer son diagnostic sans aucun écart
          lisait « Terminez une évaluation » — on lui demandait de faire ce
          qu'il venait de faire. `projected` n'existe qu'une fois une
          évaluation terminée : c'est le signal qui distingue les deux cas. */}
      {items.length === 0 ? (
        projected ? (
          <EmptyState
            title="Aucune action à mener"
            description={
              'Votre diagnostic ne fait apparaître aucun écart : il n’y a rien à ' +
              'corriger pour le moment. Refaites-le après un changement dans votre ' +
              'organisation, ou si de nouvelles mesures vous concernent.'
            }
          />
        ) : (
          <EmptyState
            title="Aucune action pour l’instant"
            description="Terminez une évaluation pour générer votre plan d’action priorisé."
          />
        )
      ) : (
        <div className="grid gap-6 md:grid-cols-3">
          {STATUSES.map((column) => (
            <div key={column.value} className="rounded-lg bg-ink-100/60 p-4">
              <h2 className="text-sm font-semibold text-ink-700">
                {column.label} ({columns[column.value].length})
              </h2>
              <div className="mt-3 space-y-3">
                {columns[column.value].map((item) => (
                  <ActionCard
                    key={item.id}
                    item={item}
                    members={members}
                    updatingId={updatingId}
                    onUpdate={updateItem}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
