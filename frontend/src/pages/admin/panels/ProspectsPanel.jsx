import { ArrowRight, CalendarClock, Plus } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../../api/endpoints'
import Field from '../../../components/admin/Field'
import Badge from '../../../components/ui/Badge'
import Button from '../../../components/ui/Button'
import Card, { CardHeader } from '../../../components/ui/Card'
import Modal from '../../../components/ui/Modal'
import { SkeletonCard } from '../../../components/ui/Skeleton'
import { useToast } from '../../../components/ui/Toast'

const STATUS_OPTIONS = [
  { value: 'new', label: 'Nouvelle' },
  { value: 'contacted', label: 'Contactée' },
  { value: 'scheduled', label: 'Démonstration planifiée' },
  { value: 'proposal', label: 'Proposition envoyée' },
  { value: 'won', label: 'Gagnée' },
  { value: 'lost', label: 'Perdue' },
  { value: 'closed', label: 'Close' },
]

const STATUS_VARIANT = {
  new: 'brand',
  contacted: 'neutral',
  scheduled: 'ok',
  proposal: 'warning',
  won: 'ok',
  lost: 'critical',
  closed: 'neutral',
}

const SIZE_OPTIONS = [
  { value: '', label: 'Non renseignée' },
  { value: '1-9', label: '1 à 9 personnes' },
  { value: '10-49', label: '10 à 49 personnes' },
  { value: '50-249', label: '50 à 249 personnes' },
  { value: '250+', label: '250 personnes et plus' },
]

function serverMessage(error, fallback) {
  const data = error?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (data && typeof data === 'object') {
    const first = Object.values(data)[0]
    if (Array.isArray(first)) return first[0]
    if (typeof first === 'string') return first
  }
  return fallback
}

const EMPTY_PROSPECT = {
  company: '',
  full_name: '',
  role: '',
  email: '',
  phone: '',
  company_size: '',
  message: '',
  next_follow_up_on: '',
}

function ProspectForm({ open, onClose, onCreated }) {
  const { showToast } = useToast()
  const [form, setForm] = useState(EMPTY_PROSPECT)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) setForm(EMPTY_PROSPECT)
  }, [open])

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = { ...form }
      if (!payload.next_follow_up_on) delete payload.next_follow_up_on
      await platformApi.createProspect(payload)
      showToast({ type: 'success', message: 'Prospect enregistré.' })
      onCreated()
      onClose()
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’enregistrement a échoué.') })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Nouveau prospect" className="max-w-2xl">
      <form noValidate onSubmit={submit} className="space-y-4">
        <p className="text-sm text-ink-600">
          Une rencontre, une recommandation, un appel entrant : tout ne passe pas par le formulaire
          du site.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Entreprise" name="company" value={form.company} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} required />
          <Field label="Contact" name="full_name" value={form.full_name} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} required />
          <Field label="Email" name="email" type="email" value={form.email} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} required />
          <Field label="Téléphone" name="phone" value={form.phone} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
          <Field label="Fonction" name="role" value={form.role} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
          <Field label="Taille" name="company_size" value={form.company_size} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} options={SIZE_OPTIONS} />
          <Field label="Relance prévue le" name="next_follow_up_on" type="date" value={form.next_follow_up_on} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
        </div>
        <Field label="Contexte" name="message" type="textarea" value={form.message} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" type="button" onClick={onClose} disabled={saving}>
            Annuler
          </Button>
          <Button type="submit" loading={saving}>
            Enregistrer
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function ProspectCard({ prospect, onChanged, onConvert }) {
  const { showToast } = useToast()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [lostReason, setLostReason] = useState('')
  const [askingReason, setAskingReason] = useState(false)

  async function patch(payload) {
    setBusy(true)
    try {
      await platformApi.updateProspect(prospect.id, payload)
      await onChanged()
      showToast({ type: 'success', message: 'Prospect mis à jour.' })
      setAskingReason(false)
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'La mise à jour a échoué.') })
    } finally {
      setBusy(false)
    }
  }

  function changeStatus(status) {
    // Une affaire perdue sans motif ne s'analyse pas six mois plus tard : le
    // serveur le refuse, l'interface demande donc le motif au bon moment.
    if (status === 'lost') {
      setAskingReason(true)
      return
    }
    patch({ status })
  }

  async function addNote(event) {
    event.preventDefault()
    if (!note.trim()) return
    setBusy(true)
    try {
      await platformApi.addProspectNote(prospect.id, note)
      setNote('')
      await onChanged()
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'La note n’a pas été ajoutée.') })
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="rounded-lg border border-ink-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-medium text-ink-900">
            {prospect.company}
            <Badge variant={STATUS_VARIANT[prospect.status] || 'neutral'}>
              {prospect.status_label}
            </Badge>
            <span className="text-xs font-normal text-ink-500">{prospect.source_label}</span>
          </p>
          <p className="mt-1 text-sm text-ink-600">
            {prospect.full_name}
            {prospect.role ? ` — ${prospect.role}` : ''} · {prospect.email}
            {prospect.phone ? ` · ${prospect.phone}` : ''}
          </p>
          {prospect.next_follow_up_on && (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-ink-500">
              <CalendarClock className="size-3.5" aria-hidden="true" />
              Relance prévue le {new Date(prospect.next_follow_up_on).toLocaleDateString('fr-FR')}
            </p>
          )}
          {prospect.lost_reason && (
            <p className="mt-1 text-xs text-ink-500">Motif : {prospect.lost_reason}</p>
          )}
          {prospect.converted_tenant_name && (
            <p className="mt-1 text-xs text-ok-strong">
              Devenu client : {prospect.converted_tenant_name}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={prospect.status}
            onChange={(event) => changeStatus(event.target.value)}
            disabled={busy}
            aria-label={`Statut de ${prospect.company}`}
            className="rounded-md border border-ink-200 px-2 py-1.5 text-sm"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={prospect.next_follow_up_on || ''}
            onChange={(event) => patch({ next_follow_up_on: event.target.value || null })}
            aria-label={`Relance de ${prospect.company}`}
            className="rounded-md border border-ink-200 px-2 py-1.5 text-sm"
          />
          {!prospect.already_client && (
            <Button variant="secondary" size="sm" icon={ArrowRight} onClick={() => onConvert(prospect)}>
              Convertir en client
            </Button>
          )}
          {prospect.already_client && (
            <span className="text-sm text-ink-500">Déjà cliente</span>
          )}
        </div>
      </div>

      {askingReason && (
        <div className="mt-3 flex flex-wrap items-end gap-2 rounded-md bg-ink-50 px-3 py-2">
          <div className="min-w-56 flex-1">
            <Field
              label="Motif de la perte"
              name="lost_reason"
              value={lostReason}
              onChange={(_n, v) => setLostReason(v)}
              hint="Obligatoire : c’est ce qu’on relira pour comprendre les affaires perdues."
            />
          </div>
          <Button size="sm" disabled={!lostReason.trim()} onClick={() => patch({ status: 'lost', lost_reason: lostReason })}>
            Enregistrer
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setAskingReason(false)}>
            Annuler
          </Button>
        </div>
      )}

      {prospect.notes?.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t border-ink-100 pt-3">
          {prospect.notes.map((entry) => (
            <li key={entry.id} className="text-sm text-ink-600">
              <span className="text-xs text-ink-400">
                {new Date(entry.created_at).toLocaleDateString('fr-FR')} · {entry.author_email} —{' '}
              </span>
              {entry.body}
            </li>
          ))}
        </ul>
      )}

      <form noValidate onSubmit={addNote} className="mt-3 flex gap-2">
        <input
          type="text"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Ajouter une note d’échange…"
          aria-label={`Note sur ${prospect.company}`}
          className="transition-smooth min-w-0 flex-1 rounded-md border border-ink-200 px-3 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-brand-600"
        />
        <Button type="submit" variant="ghost" size="sm" disabled={busy || !note.trim()}>
          Ajouter
        </Button>
      </form>
    </li>
  )
}

export default function ProspectsPanel({ onConvertToClient }) {
  const { showToast } = useToast()
  const [prospects, setProspects] = useState(null)
  const [board, setBoard] = useState(null)
  const [creating, setCreating] = useState(false)
  const [filter, setFilter] = useState('open')

  const load = useCallback(async () => {
    try {
      const params = filter === 'open' ? { open: '1' } : filter === 'all' ? {} : { status: filter }
      const [list, followUp] = await Promise.all([
        platformApi.listProspects(params),
        platformApi.followUpBoard(),
      ])
      setProspects(list.data.prospects)
      setBoard(followUp.data)
    } catch {
      showToast({ type: 'error', message: 'Impossible de charger les prospects.' })
    }
  }, [filter, showToast])

  useEffect(() => {
    load()
  }, [load])

  if (!prospects) return <SkeletonCard />

  return (
    <div className="space-y-6">
      {board && (board.due_today.length > 0 || board.stale.length > 0) && (
        <Card>
          <CardHeader title="À traiter" />
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                Relances du jour ({board.due_today.length})
              </p>
              <ul className="mt-2 space-y-1">
                {board.due_today.map((p) => (
                  <li key={p.id} className="text-sm text-ink-700">
                    {p.company} — {p.full_name}
                  </li>
                ))}
                {board.due_today.length === 0 && (
                  <li className="text-sm text-ink-500">Rien à rappeler aujourd’hui.</li>
                )}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">
                Sans activité depuis {board.stale_after_days} jours ({board.stale.length})
              </p>
              <ul className="mt-2 space-y-1">
                {board.stale.map((p) => (
                  <li key={p.id} className="text-sm text-ink-700">
                    {p.company} — {p.full_name}
                  </li>
                ))}
                {board.stale.length === 0 && (
                  <li className="text-sm text-ink-500">Aucun prospect en sommeil.</li>
                )}
              </ul>
            </div>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader
          title="Prospects"
          action={
            <span className="flex flex-wrap items-center gap-2">
              <select
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                aria-label="Filtrer les prospects"
                className="rounded-md border border-ink-200 px-2 py-1.5 text-sm"
              >
                <option value="open">En cours</option>
                <option value="all">Tous</option>
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <a
                href={platformApi.exportUrl('prospects')}
                className="transition-smooth rounded-md px-3 py-1.5 text-sm text-ink-600 hover:text-ink-900"
              >
                Exporter en CSV
              </a>
              <Button icon={Plus} size="sm" onClick={() => setCreating(true)}>
                Nouveau prospect
              </Button>
            </span>
          }
        />

        <ul className="space-y-3">
          {prospects.map((prospect) => (
            <ProspectCard
              key={prospect.id}
              prospect={prospect}
              onChanged={load}
              onConvert={onConvertToClient}
            />
          ))}
        </ul>
        {prospects.length === 0 && (
          <p className="py-6 text-center text-sm text-ink-500">Aucun prospect pour ce filtre.</p>
        )}
      </Card>

      <ProspectForm open={creating} onClose={() => setCreating(false)} onCreated={load} />
    </div>
  )
}
