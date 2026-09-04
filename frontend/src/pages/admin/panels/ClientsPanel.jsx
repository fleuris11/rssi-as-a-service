import { Archive, ArrowLeft, KeyRound, Plus, UserPlus } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../../api/endpoints'
import ConfirmDialog from '../../../components/admin/ConfirmDialog'
import DataTable from '../../../components/admin/DataTable'
import Field from '../../../components/admin/Field'
import InvitationResult from '../../../components/admin/InvitationResult'
import Badge from '../../../components/ui/Badge'
import Button from '../../../components/ui/Button'
import Card, { CardHeader } from '../../../components/ui/Card'
import Modal from '../../../components/ui/Modal'
import { SkeletonCard } from '../../../components/ui/Skeleton'
import { useToast } from '../../../components/ui/Toast'

const STATUS_VARIANT = {
  active: 'ok',
  trial: 'brand',
  suspended: 'warning',
  cancelled: 'neutral',
  expired: 'critical',
}

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Administrateur' },
  { value: 'contributor', label: 'Contributeur' },
  { value: 'reader', label: 'Lecteur' },
]

/** Message d'erreur du serveur, tel quel. Le résumer perdrait l'information
 *  utile : un refus de capacité dit ce qu'il reste et ce qu'il faut libérer. */
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

// --- Création d'un client ---------------------------------------------------

const EMPTY_CLIENT = {
  name: '',
  owner_email: '',
  owner_first_name: '',
  owner_last_name: '',
  plan_code: '',
  engagement: 'trial',
  sector: '',
  headcount: '',
  contact_phone: '',
  website: '',
  account_manager: '',
  internal_notes: '',
}

export function ClientCreateModal({ open, onClose, plans, prefill, onCreated }) {
  const { showToast } = useToast()
  const [form, setForm] = useState(EMPTY_CLIENT)
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [invitation, setInvitation] = useState(null)

  useEffect(() => {
    if (!open) return
    // Conversion d'un prospect : le formulaire arrive pré-rempli. Retaper des
    // informations déjà saisies est le meilleur moyen d'en perdre.
    setForm({ ...EMPTY_CLIENT, ...(prefill || {}) })
    setErrors({})
    setInvitation(null)
  }, [open, prefill])

  function update(name, value) {
    setForm((previous) => ({ ...previous, [name]: value }))
    setErrors((previous) => ({ ...previous, [name]: '' }))
  }

  async function submit(event) {
    event.preventDefault()
    const nextErrors = {}
    if (!form.name.trim()) nextErrors.name = 'Le nom de l’entreprise est obligatoire.'
    if (!form.owner_email.trim()) nextErrors.owner_email = 'L’email du premier utilisateur est obligatoire.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSaving(true)
    try {
      const payload = { ...form }
      if (payload.headcount === '') delete payload.headcount
      if (!payload.plan_code) delete payload.plan_code
      const response = await platformApi.createClient(payload)
      setInvitation(response.data.invitation)
      showToast({ type: 'success', message: `${response.data.name} créée.` })
      onCreated?.()
    } catch (error) {
      showToast({
        type: 'error',
        message: serverMessage(error, 'La création a échoué.'),
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Nouveau client" className="max-w-2xl">
      {invitation ? (
        <div className="space-y-4">
          <InvitationResult invitation={invitation} />
          <div className="flex justify-end">
            <Button onClick={onClose}>Terminé</Button>
          </div>
        </div>
      ) : (
        <form noValidate onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Nom de l’entreprise" name="name" value={form.name} onChange={update} error={errors.name} required />
            <Field label="Secteur" name="sector" value={form.sector} onChange={update} />
            <Field
              label="Email du premier utilisateur"
              name="owner_email"
              type="email"
              value={form.owner_email}
              onChange={update}
              error={errors.owner_email}
              required
              hint="Il recevra un lien pour définir son mot de passe. Aucun mot de passe n’est choisi ici."
            />
            <Field label="Effectif" name="headcount" type="number" value={form.headcount} onChange={update} />
            <Field label="Prénom" name="owner_first_name" value={form.owner_first_name} onChange={update} />
            <Field label="Nom" name="owner_last_name" value={form.owner_last_name} onChange={update} />
            <Field
              label="Offre"
              name="plan_code"
              value={form.plan_code}
              onChange={update}
              options={[
                { value: '', label: 'Offre par défaut' },
                ...plans.map((plan) => ({
                  value: plan.code,
                  label: `${plan.name} — ${plan.monitored_assets} emplacement(s)`,
                })),
              ]}
            />
            <Field
              label="Engagement"
              name="engagement"
              value={form.engagement}
              onChange={update}
              options={[
                { value: 'trial', label: 'Période d’essai' },
                { value: 'active', label: 'Abonnement actif' },
              ]}
            />
            <Field label="Téléphone" name="contact_phone" value={form.contact_phone} onChange={update} />
            <Field label="Référent commercial" name="account_manager" value={form.account_manager} onChange={update} />
          </div>
          <Field label="Notes internes" name="internal_notes" type="textarea" value={form.internal_notes} onChange={update} />

          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose} type="button" disabled={saving}>
              Annuler
            </Button>
            <Button type="submit" loading={saving}>
              Créer le client
            </Button>
          </div>
        </form>
      )}
    </Modal>
  )
}

// --- Fiche d'un client ------------------------------------------------------

function MembersSection({ tenantId, quota, onChanged }) {
  const { showToast } = useToast()
  const [members, setMembers] = useState([])
  const [form, setForm] = useState({ email: '', role: 'reader' })
  const [invitation, setInvitation] = useState(null)
  const [busy, setBusy] = useState(null)
  const [confirm, setConfirm] = useState(null)

  const load = useCallback(async () => {
    const response = await platformApi.listMembers(tenantId)
    setMembers(response.data)
  }, [tenantId])

  useEffect(() => {
    load()
  }, [load])

  async function invite(event) {
    event.preventDefault()
    setBusy('invite')
    try {
      const response = await platformApi.inviteMember(tenantId, form)
      setInvitation(response.data.invitation)
      setForm({ email: '', role: 'reader' })
      await load()
      onChanged?.()
      showToast({ type: 'success', message: 'Utilisateur invité.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’invitation a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  async function act(membership, payload, successMessage) {
    setBusy(membership.id)
    try {
      await platformApi.updateMember(tenantId, membership.id, payload)
      await load()
      showToast({ type: 'success', message: successMessage })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’opération a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  async function resetPassword(membership) {
    setBusy(membership.id)
    try {
      const response = await platformApi.resetMemberPassword(tenantId, membership.id)
      setInvitation(response.data)
      showToast({ type: 'success', message: 'Lien de réinitialisation émis.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’émission a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  async function remove() {
    const membership = confirm
    setBusy(membership.id)
    try {
      await platformApi.removeMember(tenantId, membership.id)
      setConfirm(null)
      // Le lien d'invitation affiche l'adresse de la personne : le laisser
      // après son retrait laisse croire que son accès est toujours en cours
      // d'ouverture.
      setInvitation(null)
      await load()
      onChanged?.()
      showToast({ type: 'success', message: `${membership.email} retiré.` })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'Le retrait a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Utilisateurs"
        action={<span className="text-xs text-ink-500">{members.length} / {quota || '∞'}</span>}
      />

      {invitation && (
        <div className="mb-4">
          <InvitationResult invitation={invitation} />
        </div>
      )}

      <ul className="mb-4 space-y-2">
        {members.map((member) => (
          <li
            key={member.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-ink-200 px-3 py-2"
          >
            <span className="min-w-0">
              <span className="block truncate text-sm text-ink-800">{member.email}</span>
              <span className="text-xs text-ink-500">
                {member.role_label}
                {!member.has_usable_password && ' · invitation en attente'}
                {member.has_usable_password && !member.is_active && ' · accès coupé'}
              </span>
            </span>
            <span className="flex flex-wrap items-center gap-2">
              <select
                value={member.role}
                onChange={(event) => act(member, { role: event.target.value }, 'Rôle modifié.')}
                disabled={busy === member.id}
                aria-label={`Rôle de ${member.email}`}
                className="rounded-md border border-ink-200 px-2 py-1 text-xs"
              >
                {ROLE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <Button
                variant="ghost"
                size="sm"
                icon={KeyRound}
                disabled={busy === member.id}
                onClick={() => resetPassword(member)}
              >
                Réinitialiser
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy === member.id}
                onClick={() =>
                  act(
                    member,
                    { is_active: !member.is_active },
                    member.is_active ? 'Accès coupé.' : 'Accès rétabli.'
                  )
                }
              >
                {member.is_active ? 'Désactiver' : 'Réactiver'}
              </Button>
              <Button
                variant="danger"
                size="sm"
                disabled={busy === member.id}
                onClick={() => setConfirm(member)}
              >
                Retirer
              </Button>
            </span>
          </li>
        ))}
      </ul>

      <form noValidate onSubmit={invite} className="flex flex-wrap items-end gap-3 border-t border-ink-100 pt-4">
        <div className="min-w-56 flex-1">
          <Field
            label="Inviter un utilisateur"
            name="email"
            type="email"
            value={form.email}
            onChange={(name, value) => setForm((p) => ({ ...p, [name]: value }))}
            required
          />
        </div>
        <div className="w-44">
          <Field
            label="Rôle"
            name="role"
            value={form.role}
            onChange={(name, value) => setForm((p) => ({ ...p, [name]: value }))}
            options={ROLE_OPTIONS}
          />
        </div>
        <Button type="submit" icon={UserPlus} loading={busy === 'invite'}>
          Inviter
        </Button>
      </form>

      <ConfirmDialog
        open={Boolean(confirm)}
        onClose={() => setConfirm(null)}
        onConfirm={remove}
        danger
        title="Retirer cet utilisateur ?"
        summary={`${confirm?.email} n'aura plus accès à l'espace de cette entreprise.`}
        consequences={[
          'Son compte est conservé : il peut appartenir à d’autres entreprises.',
          'Son historique d’actions reste attribuable.',
        ]}
        confirmLabel="Retirer"
        loading={busy === confirm?.id}
      />
    </Card>
  )
}

function SubscriptionSection({ tenant, plans, onChanged }) {
  const { showToast } = useToast()
  const subscription = tenant.subscription
  const [form, setForm] = useState({})
  const [busy, setBusy] = useState(false)

  // Dépendances volontairement limitées à l'IDENTITÉ de l'abonnement, pas à
  // l'objet : la fiche se recharge quand une AUTRE section agit (inviter un
  // utilisateur, par exemple), et repartir des valeurs serveur à ce
  // moment-là effacerait sans un mot les quotas que l'on est en train de
  // saisir. On ne réinitialise donc que si l'abonnement change réellement
  // d'offre ou d'état — les deux cas où les quotas affichés ne veulent plus
  // rien dire.
  const subscriptionId = subscription?.id
  const planCode = subscription?.plan_code
  const subscriptionStatus = subscription?.status

  useEffect(() => {
    if (!subscription) return
    setForm({
      override_monitored_assets: subscription.quotas.monitored_assets,
      override_monthly_scans: subscription.quotas.monthly_scans,
      override_max_users: subscription.quotas.max_users,
      trial_ends_at: subscription.trial_ends_at ? subscription.trial_ends_at.slice(0, 10) : '',
      internal_notes: subscription.internal_notes || '',
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subscriptionId, planCode, subscriptionStatus])

  if (!subscription) {
    return (
      <Card>
        <CardHeader title="Abonnement" />
        <p className="text-sm text-ink-500">Cette entreprise n’a pas d’abonnement.</p>
      </Card>
    )
  }

  async function transition(action, extra = {}) {
    setBusy(true)
    try {
      await platformApi.subscriptionAction(tenant.id, { action, ...extra })
      await onChanged()
      showToast({ type: 'success', message: 'Abonnement mis à jour.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’opération a échoué.') })
    } finally {
      setBusy(false)
    }
  }

  async function saveQuotas(event) {
    event.preventDefault()
    setBusy(true)
    try {
      const payload = {
        override_monitored_assets: Number(form.override_monitored_assets),
        override_monthly_scans: Number(form.override_monthly_scans),
        override_max_users: Number(form.override_max_users),
        internal_notes: form.internal_notes,
      }
      if (form.trial_ends_at && subscription.status === 'trial') {
        payload.trial_ends_at = new Date(`${form.trial_ends_at}T12:00:00`).toISOString()
      }
      await platformApi.updateSubscription(tenant.id, payload)
      await onChanged()
      showToast({ type: 'success', message: 'Quotas et notes enregistrés.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’enregistrement a échoué.') })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Abonnement"
        action={
          <Badge variant={STATUS_VARIANT[subscription.status] || 'neutral'}>
            {subscription.status_label}
          </Badge>
        }
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="w-56">
          <Field
            label="Offre"
            name="plan"
            value={subscription.plan_code}
            onChange={(_name, value) => transition('change_plan', { plan_code: value })}
            options={plans.map((plan) => ({
              value: plan.code,
              label: `${plan.name} — ${plan.monitored_assets} empl.`,
            }))}
            disabled={busy}
            hint="Les quotas négociés sont remis à ceux de la nouvelle offre."
          />
        </div>
        <span className="flex flex-wrap gap-2 pb-1">
          {subscription.status !== 'active' && (
            <Button size="sm" disabled={busy} onClick={() => transition('activate')}>
              Activer
            </Button>
          )}
          {subscription.status !== 'suspended' && (
            <Button variant="secondary" size="sm" disabled={busy} onClick={() => transition('suspend')}>
              Suspendre
            </Button>
          )}
          {subscription.status !== 'cancelled' && (
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => transition('cancel')}>
              Résilier
            </Button>
          )}
        </span>
      </div>

      <form noValidate onSubmit={saveQuotas} className="space-y-4 border-t border-ink-100 pt-4">
        <p className="text-sm text-ink-600">
          Quotas de ce client. Ils partent de l’offre et peuvent être négociés individuellement —
          indispensable pour un palier sur devis. Une hausse d’emplacements est vérifiée contre le
          pool partagé de la plateforme.
        </p>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field
            label="Emplacements surveillés"
            name="override_monitored_assets"
            type="number"
            value={form.override_monitored_assets}
            onChange={(name, value) => setForm((p) => ({ ...p, [name]: value }))}
          />
          <Field
            label="Analyses par mois"
            name="override_monthly_scans"
            type="number"
            value={form.override_monthly_scans}
            onChange={(name, value) => setForm((p) => ({ ...p, [name]: value }))}
            hint="0 = illimité"
          />
          <Field
            label="Utilisateurs"
            name="override_max_users"
            type="number"
            value={form.override_max_users}
            onChange={(name, value) => setForm((p) => ({ ...p, [name]: value }))}
            hint="0 = illimité"
          />
        </div>
        {subscription.status === 'trial' && (
          <Field
            label="Fin de la période d’essai"
            name="trial_ends_at"
            type="date"
            value={form.trial_ends_at}
            onChange={(name, value) => setForm((p) => ({ ...p, [name]: value }))}
          />
        )}
        <Field
          label="Notes internes sur l’abonnement"
          name="internal_notes"
          type="textarea"
          value={form.internal_notes}
          onChange={(name, value) => setForm((p) => ({ ...p, [name]: value }))}
        />
        <div className="flex justify-end">
          <Button type="submit" loading={busy}>
            Enregistrer
          </Button>
        </div>
      </form>
    </Card>
  )
}

function ActionsSection({ tenant, onChanged }) {
  const { showToast } = useToast()
  const [busy, setBusy] = useState(null)
  const [confirm, setConfirm] = useState(null)

  async function run(action, message) {
    setBusy(action)
    try {
      await platformApi.clientAction(tenant.id, action)
      setConfirm(null)
      await onChanged()
      showToast({ type: 'success', message })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’action a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card>
      <CardHeader title="Actions sur les données" />
      <p className="mb-4 text-sm text-ink-600">
        Ces actions se déclenchent sans donner accès au contenu des compromissions du client
        (ADR-014). Vous lancez le traitement, vous n’en lisez pas le résultat.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" loading={busy === 'scan'} onClick={() => run('scan', 'Analyse lancée.')}>
          Lancer une analyse
        </Button>
        <Button
          variant="secondary"
          size="sm"
          loading={busy === 'refresh_synthesis'}
          onClick={() => run('refresh_synthesis', 'Synthèse en cours de régénération.')}
        >
          Régénérer la synthèse
        </Button>
        <Button variant="danger" size="sm" onClick={() => setConfirm('purge')}>
          Purger les mots de passe
        </Button>
      </div>

      <ConfirmDialog
        open={confirm === 'purge'}
        onClose={() => setConfirm(null)}
        onConfirm={() => run('purge_secrets', 'Mots de passe effacés.')}
        danger
        title="Purger les mots de passe fuités ?"
        summary={`Tous les mots de passe encore chiffrés de ${tenant.name} seront effacés.`}
        consequences={[
          'Les fuites elles-mêmes sont conservées : dates, sources, statut, historique.',
          'Seule la valeur du mot de passe disparaît, définitivement.',
          'Le client verra « mot de passe effacé » à la place de la valeur.',
        ]}
        confirmLabel="Purger"
        loading={busy === 'purge_secrets'}
      />
    </Card>
  )
}

/**
 * Conversions entre ce qui est STOCKÉ (des minutes, toujours) et ce qui est
 * SAISI (une valeur plus une unité).
 *
 * La minute est l'unité canonique du produit — modèle, réglage de plateforme,
 * API, cache. L'heure n'existe qu'ici, à la saisie, parce que « 1440 minutes »
 * ne se lit pas comme 24 h.
 *
 * Le zéro est le piège, et il se rejoue à chaque couche traversée : `null`
 * veut dire « pas de surcharge, on applique le réglage de plateforme », `0`
 * veut dire « aucun délai, décidé pour ce client ». D'où les comparaisons
 * explicites à `null`/`''` plutôt que des tests de vérité — un `||` bien
 * innocent transformerait 0 en vide et ferait retomber sur 24 h un client à
 * qui l'exploitant vient d'accorder l'inverse.
 */
export function minutesVersSaisie(minutes) {
  if (minutes === null || minutes === undefined) return { valeur: '', unite: 'minutes' }
  if (minutes !== 0 && minutes % 60 === 0) return { valeur: minutes / 60, unite: 'heures' }
  return { valeur: minutes, unite: 'minutes' }
}

export function saisieVersMinutes(valeur, unite) {
  if (valeur === '' || valeur === null || valeur === undefined) return null
  const n = Number(valeur)
  if (Number.isNaN(n)) return null
  return unite === 'heures' ? n * 60 : n
}

export function ClientDetail({ tenantId, plans, onBack, onChanged }) {
  const { showToast } = useToast()
  const [tenant, setTenant] = useState(null)
  const [fiche, setFiche] = useState(null)
  const [form, setForm] = useState({})
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(null)

  const load = useCallback(async () => {
    const response = await platformApi.clientDetail(tenantId)
    setTenant(response.data)
    setFiche(response.data.fiche)
    setForm({
      name: response.data.fiche.name,
      sector: response.data.fiche.sector || '',
      headcount: response.data.fiche.headcount ?? '',
      contact_email: response.data.fiche.contact_email || '',
      contact_phone: response.data.fiche.contact_phone || '',
      address: response.data.fiche.address || '',
      website: response.data.fiche.website || '',
      account_manager: response.data.fiche.account_manager || '',
      internal_notes: response.data.fiche.internal_notes || '',
      // Chaîne vide = pas de surcharge (le réglage de plateforme s'applique).
      // Le zéro, lui, est une VALEUR : « aucun délai pour ce client ».
      // `?? ''` et non `|| ''` — sinon 0 deviendrait vide, et l'exploitant
      // qui accorde « aucun délai » verrait sa décision retomber sur 24 h.
      //
      // Stocké en MINUTES ; on propose l'heure à la saisie quand la valeur
      // tombe juste, parce que « 1440 minutes » ne se lit pas comme 24 h.
      scan_cooldown_value: minutesVersSaisie(response.data.fiche.scan_cooldown_minutes).valeur,
      scan_cooldown_unite: minutesVersSaisie(response.data.fiche.scan_cooldown_minutes).unite,
    })
  }, [tenantId])

  useEffect(() => {
    load()
  }, [load])

  if (!tenant) return <SkeletonCard />

  async function saveRecord(event) {
    event.preventDefault()
    setBusy(true)
    try {
      const payload = { ...form }
      if (payload.headcount === '') payload.headcount = null
      // Vide -> null : on retire la surcharge et le client repasse sous le
      // réglage de plateforme. Toute autre valeur, zéro compris, est envoyée,
      // convertie dans l'unité canonique du produit : la minute.
      payload.scan_cooldown_minutes = saisieVersMinutes(
        payload.scan_cooldown_value,
        payload.scan_cooldown_unite
      )
      delete payload.scan_cooldown_value
      delete payload.scan_cooldown_unite
      await platformApi.updateClient(tenantId, payload)
      await load()
      onChanged?.()
      showToast({ type: 'success', message: 'Fiche enregistrée.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’enregistrement a échoué.') })
    } finally {
      setBusy(false)
    }
  }

  async function archive(restore) {
    setBusy(true)
    try {
      await platformApi.archiveClient(tenantId, restore ? { restore: true } : {})
      setConfirm(null)
      await load()
      onChanged?.()
      showToast({ type: 'success', message: restore ? 'Entreprise restaurée.' : 'Entreprise archivée.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’opération a échoué.') })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="ghost" icon={ArrowLeft} onClick={onBack}>
          Retour aux clients
        </Button>
        <span className="flex gap-2">
          {fiche?.is_archived ? (
            <Button variant="secondary" onClick={() => archive(true)} loading={busy}>
              Restaurer
            </Button>
          ) : (
            <Button variant="secondary" icon={Archive} onClick={() => setConfirm('archive')}>
              Archiver
            </Button>
          )}
        </span>
      </div>

      <div>
        <h2 className="font-display text-xl font-semibold text-ink-900">{tenant.name}</h2>
        <p className="mt-1 text-sm text-ink-500">
          {tenant.usage.users} utilisateur(s) · {tenant.usage.assets} actif(s) ·{' '}
          {tenant.usage.monitored_assets} surveillé(s) · {tenant.usage.findings_total} exposition(s)
        </p>
      </div>

      <Card>
        <CardHeader title="Fiche entreprise" />
        <form noValidate onSubmit={saveRecord} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Raison sociale" name="name" value={form.name} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} required />
            <Field label="Secteur" name="sector" value={form.sector} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
            <Field label="Email de contact" name="contact_email" type="email" value={form.contact_email} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
            <Field label="Téléphone" name="contact_phone" value={form.contact_phone} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
            <Field label="Effectif" name="headcount" type="number" value={form.headcount} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
            <Field label="Site web" name="website" value={form.website} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
            <Field label="Référent commercial" name="account_manager" value={form.account_manager} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
          </div>
          <Field label="Adresse" name="address" type="textarea" rows={2} value={form.address} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />

          <div className="rounded-md border border-ink-200 bg-ink-50/60 p-4">
            <p className="text-sm font-medium text-ink-800">Délai entre deux analyses</p>
            <p className="mt-1 text-sm text-ink-600">
              Temps d’attente imposé à ce client entre deux analyses lancées depuis son
              espace. Il protège le budget de requêtes partagé, pas le client.
            </p>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <div className="w-40">
                <Field
                  label="Valeur (vide = réglage de la plateforme)"
                  name="scan_cooldown_value"
                  type="number"
                  value={form.scan_cooldown_value}
                  onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))}
                />
              </div>
              <div className="w-36">
                <label
                  className="block text-sm font-medium text-ink-700"
                  htmlFor="scan_cooldown_unite"
                >
                  Unité
                </label>
                <select
                  id="scan_cooldown_unite"
                  className="transition-smooth mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600"
                  value={form.scan_cooldown_unite || 'minutes'}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, scan_cooldown_unite: e.target.value }))
                  }
                >
                  <option value="minutes">minutes</option>
                  <option value="heures">heures</option>
                </select>
              </div>
            </div>
            <p className="mt-2 text-xs text-ink-500">
              Actuellement appliqué :{' '}
              <strong>{fiche?.effective_scan_cooldown_label}</strong>
              {form.scan_cooldown_value === ''
                ? ' (réglage de la plateforme)'
                : ' (propre à ce client)'}
              . Saisir <strong>0</strong> retire tout délai pour ce client.
            </p>
          </div>
          <Field label="Notes internes" name="internal_notes" type="textarea" value={form.internal_notes} onChange={(n, v) => setForm((p) => ({ ...p, [n]: v }))} />
          <div className="flex justify-end">
            <Button type="submit" loading={busy}>
              Enregistrer la fiche
            </Button>
          </div>
        </form>
      </Card>

      <SubscriptionSection tenant={tenant} plans={plans} onChanged={load} />
      <MembersSection
        tenantId={tenantId}
        quota={tenant.subscription?.quotas?.max_users}
        onChanged={load}
      />
      <ActionsSection tenant={tenant} onChanged={load} />

      <ConfirmDialog
        open={confirm === 'archive'}
        onClose={() => setConfirm(null)}
        onConfirm={() => archive(false)}
        title="Archiver cette entreprise ?"
        summary={`${tenant.name} sortira des listes actives.`}
        consequences={[
          'Son abonnement est résilié : ses emplacements retournent au pool partagé.',
          'Aucune donnée n’est détruite — l’archivage se défait.',
          'Elle apparaîtra dans la corbeille, où la suppression définitive est possible.',
        ]}
        confirmLabel="Archiver"
        loading={busy}
      />
    </div>
  )
}

// --- Liste ------------------------------------------------------------------

export default function ClientsPanel({
  tenants,
  plans,
  onRefresh,
  prefill,
  onPrefillConsumed,
  initialTenantId = null,
  onFocusConsumed,
}) {
  // La recherche globale ouvre directement une fiche : arriver sur la liste
  // puis devoir y retrouver l'entreprise qu'on vient de nommer annulerait
  // l'intérêt de la recherche.
  const [selected, setSelected] = useState(initialTenantId)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    if (prefill) setCreating(true)
  }, [prefill])

  if (selected) {
    return (
      <ClientDetail
        tenantId={selected}
        plans={plans}
        onBack={() => {
          setSelected(null)
          onFocusConsumed?.()
        }}
        onChanged={onRefresh}
      />
    )
  }

  const columns = [
    { key: 'name', label: 'Entreprise' },
    { key: 'plan_name', label: 'Offre', render: (row) => row.plan_name || '—' },
    {
      key: 'subscription_status',
      label: 'État',
      render: (row) => (
        <Badge variant={STATUS_VARIANT[row.subscription_status] || 'neutral'}>
          {row.subscription_status_label}
        </Badge>
      ),
    },
    { key: 'monitored_assets_quota', label: 'Emplacements' },
    { key: 'user_count', label: 'Utilisateurs' },
  ]

  return (
    <Card>
      <CardHeader
        title="Clients"
        action={
          <span className="flex gap-2">
            <a
              href={platformApi.exportUrl('tenants')}
              className="transition-smooth rounded-md px-3 py-1.5 text-sm text-ink-600 hover:text-ink-900"
            >
              Exporter en CSV
            </a>
            <Button icon={Plus} size="sm" onClick={() => setCreating(true)}>
              Nouveau client
            </Button>
          </span>
        }
      />
      <DataTable
        columns={columns}
        rows={tenants}
        getRowKey={(row) => row.id}
        onRowClick={(row) => setSelected(row.id)}
        searchKeys={['name', 'plan_name']}
        initialSort={{ key: 'name', direction: 'asc' }}
        emptyMessage="Aucun client. Créez-en un ou convertissez un prospect."
      />

      <ClientCreateModal
        open={creating}
        onClose={() => {
          setCreating(false)
          onPrefillConsumed?.()
        }}
        plans={plans}
        prefill={prefill}
        onCreated={onRefresh}
      />
    </Card>
  )
}
