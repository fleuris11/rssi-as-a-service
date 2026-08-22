import { RotateCcw, Trash2, UserPlus } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { platformApi } from '../../../api/endpoints'
import ConfirmDialog from '../../../components/admin/ConfirmDialog'
import Field from '../../../components/admin/Field'
import InvitationResult from '../../../components/admin/InvitationResult'
import Badge from '../../../components/ui/Badge'
import Button from '../../../components/ui/Button'
import Card, { CardHeader } from '../../../components/ui/Card'
import { SkeletonCard } from '../../../components/ui/Skeleton'
import { useToast } from '../../../components/ui/Toast'

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

// --- Administrateurs de la plateforme ---------------------------------------

export function AdminsPanel() {
  const { showToast } = useToast()
  const [data, setData] = useState(null)
  const [form, setForm] = useState({ email: '', level: 'commercial' })
  const [invitation, setInvitation] = useState(null)
  const [busy, setBusy] = useState(null)
  const [revoking, setRevoking] = useState(null)

  const load = useCallback(async () => {
    const response = await platformApi.listAdmins()
    setData(response.data)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (!data) return <SkeletonCard />

  async function invite(event) {
    event.preventDefault()
    setBusy('invite')
    try {
      const response = await platformApi.inviteAdmin(form)
      setInvitation(response.data.invitation)
      setForm({ email: '', level: 'commercial' })
      await load()
      showToast({ type: 'success', message: 'Administrateur invité.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’invitation a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  async function changeLevel(admin, level) {
    setBusy(admin.id)
    try {
      await platformApi.changeAdminLevel(admin.id, level)
      await load()
      showToast({ type: 'success', message: 'Niveau modifié.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'La modification a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  async function revoke() {
    setBusy(revoking.id)
    try {
      await platformApi.revokeAdmin(revoking.id)
      setRevoking(null)
      await load()
      showToast({ type: 'success', message: 'Droits retirés.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'Le retrait a échoué.') })
      setRevoking(null)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card>
      <CardHeader title="Administrateurs de la plateforme" />
      <p className="mb-4 text-sm text-ink-600">
        Un administrateur complet accède à tout, y compris la configuration et cette page. Un
        commercial consulte tous les écrans et gère les prospects, sans pouvoir toucher aux clients
        ni au catalogue.
      </p>

      {invitation && (
        <div className="mb-4">
          <InvitationResult invitation={invitation} />
        </div>
      )}

      <ul className="mb-4 space-y-2">
        {data.admins.map((admin) => (
          <li
            key={admin.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-ink-200 px-3 py-2"
          >
            <span className="min-w-0">
              <span className="block truncate text-sm text-ink-800">{admin.email}</span>
              <span className="text-xs text-ink-500">
                {admin.name && `${admin.name} · `}
                {admin.has_usable_password ? 'compte actif' : 'invitation en attente'}
                {admin.last_login &&
                  ` · dernière connexion le ${new Date(admin.last_login).toLocaleDateString('fr-FR')}`}
              </span>
            </span>
            <span className="flex items-center gap-2">
              <Badge variant={admin.level === 'full' ? 'brand' : 'neutral'}>
                {admin.level_label}
              </Badge>
              <select
                value={admin.level}
                onChange={(event) => changeLevel(admin, event.target.value)}
                disabled={busy === admin.id}
                aria-label={`Niveau de ${admin.email}`}
                className="rounded-md border border-ink-200 px-2 py-1 text-xs"
              >
                {data.levels.map((level) => (
                  <option key={level.value} value={level.value}>
                    {level.label}
                  </option>
                ))}
              </select>
              <Button
                variant="danger"
                size="sm"
                disabled={busy === admin.id}
                onClick={() => setRevoking(admin)}
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
            label="Inviter un administrateur"
            name="email"
            type="email"
            value={form.email}
            onChange={(name, value) => setForm((p) => ({ ...p, [name]: value }))}
            required
          />
        </div>
        <div className="w-56">
          <Field
            label="Niveau"
            name="level"
            value={form.level}
            onChange={(name, value) => setForm((p) => ({ ...p, [name]: value }))}
            options={data.levels.map((level) => ({ value: level.value, label: level.label }))}
          />
        </div>
        <Button type="submit" icon={UserPlus} loading={busy === 'invite'}>
          Inviter
        </Button>
      </form>

      <ConfirmDialog
        open={Boolean(revoking)}
        onClose={() => setRevoking(null)}
        onConfirm={revoke}
        danger
        title="Retirer ces droits d’administration ?"
        summary={`${revoking?.email} n'aura plus accès à cette console.`}
        consequences={[
          'Son compte utilisateur est conservé : il peut être membre d’une entreprise cliente.',
          'L’opération est refusée s’il s’agit du dernier administrateur complet.',
        ]}
        confirmLabel="Retirer les droits"
        loading={busy === revoking?.id}
      />
    </Card>
  )
}

// --- Réglages d'exploitation ------------------------------------------------

export function SettingsPanel({ configuration }) {
  const { showToast } = useToast()
  const [settings, setSettings] = useState(null)
  const [drafts, setDrafts] = useState({})
  const [busy, setBusy] = useState(null)
  const [confirm, setConfirm] = useState(null)

  const load = useCallback(async () => {
    const response = await platformApi.settings()
    setSettings(response.data.settings)
    setDrafts(Object.fromEntries(response.data.settings.map((s) => [s.key, s.value])))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (!settings) return <SkeletonCard />

  async function save(setting) {
    setBusy(setting.key)
    try {
      const response = await platformApi.updateSetting(setting.key, drafts[setting.key])
      setSettings(response.data.settings)
      setConfirm(null)
      showToast({
        type: response.data.warning ? 'warning' : 'success',
        message: response.data.warning || 'Réglage enregistré.',
      })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’enregistrement a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  async function reset(setting) {
    setBusy(setting.key)
    try {
      const response = await platformApi.resetSetting(setting.key)
      setSettings(response.data.settings)
      setDrafts(Object.fromEntries(response.data.settings.map((s) => [s.key, s.value])))
      showToast({ type: 'success', message: 'Valeur du fichier d’environnement rétablie.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'Le retour en arrière a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  const groups = settings.reduce((acc, setting) => {
    ;(acc[setting.group] ||= []).push(setting)
    return acc
  }, {})

  return (
    <div className="space-y-6">
      {Object.entries(groups).map(([group, rows]) => (
        <Card key={group}>
          <CardHeader title={group} />
          <div className="space-y-4">
            {rows.map((setting) => (
              <div key={setting.key} className="border-b border-ink-100 pb-4 last:border-0 last:pb-0">
                <div className="flex flex-wrap items-end gap-3">
                  <div className="min-w-56 flex-1">
                    <Field
                      label={setting.label}
                      name={setting.key}
                      type={setting.kind === 'bool' ? 'checkbox' : setting.kind === 'int' ? 'number' : 'text'}
                      value={drafts[setting.key]}
                      onChange={(name, value) => setDrafts((p) => ({ ...p, [name]: value }))}
                      hint={setting.help_text}
                    />
                  </div>
                  <span className="flex gap-2 pb-1">
                    <Button
                      size="sm"
                      loading={busy === setting.key}
                      onClick={() => (setting.sensitive ? setConfirm(setting) : save(setting))}
                    >
                      Enregistrer
                    </Button>
                    {setting.is_overridden && (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={RotateCcw}
                        disabled={busy === setting.key}
                        onClick={() => reset(setting)}
                      >
                        Défaut
                      </Button>
                    )}
                  </span>
                </div>
                {setting.is_overridden && (
                  <p className="mt-1 text-xs text-ink-500">
                    Valeur du fichier d’environnement : {String(setting.default)}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Card>
      ))}

      <Card>
        <CardHeader title="Clés et secrets" />
        <p className="mb-4 text-sm text-ink-600">
          Les secrets restent en variables d’environnement et ne sont pas modifiables ici : les
          stocker en base les exposerait à toute sauvegarde et à toute injection SQL. Cette page
          n’en montre que la présence et la validité.
        </p>
        <ul className="space-y-2">
          {(configuration?.keys || []).map((key) => (
            <li
              key={key.name}
              className="flex items-center justify-between gap-3 rounded-md bg-ink-50 px-3 py-2"
            >
              <span className="text-sm text-ink-800">{key.label}</span>
              <Badge variant={key.present && key.valid ? 'ok' : 'critical'} dot>
                {key.present ? (key.valid ? 'Configurée' : 'Format invalide') : 'Absente'}
              </Badge>
            </li>
          ))}
        </ul>
      </Card>

      <ConfirmDialog
        open={Boolean(confirm)}
        onClose={() => setConfirm(null)}
        onConfirm={() => save(confirm)}
        title={`Modifier « ${confirm?.label} » ?`}
        summary={confirm?.help_text}
        consequences={[
          `Nouvelle valeur : ${String(drafts[confirm?.key])}.`,
          'Les engagements déjà pris envers vos clients sont honorés : aucune baisse ne leur retire quoi que ce soit.',
          'Le réglage prend effet immédiatement, sans redémarrage.',
        ]}
        confirmLabel="Appliquer"
        loading={busy === confirm?.key}
      />
    </div>
  )
}

// --- Corbeille --------------------------------------------------------------

export function TrashPanel({ onRefresh }) {
  const { showToast } = useToast()
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const load = useCallback(async () => {
    const response = await platformApi.trash()
    setData(response.data)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (!data) return <SkeletonCard />

  async function restore(row) {
    setBusy(row.id)
    try {
      await platformApi.archiveClient(row.id, { restore: true })
      await load()
      onRefresh?.()
      showToast({ type: 'success', message: `${row.name} restaurée.` })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'La restauration a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  async function destroy() {
    setBusy(deleting.id)
    try {
      await platformApi.deleteClient(deleting.id, deleting.name)
      setDeleting(null)
      await load()
      onRefresh?.()
      showToast({ type: 'success', message: 'Entreprise supprimée définitivement.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'La suppression a échoué.') })
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card>
      <CardHeader title="Corbeille" />
      <p className="mb-4 text-sm text-ink-600">
        Les entreprises archivées restent restaurables. Au-delà de {data.retention_days} jours, la
        suppression définitive devient possible — elle détruit les diagnostics, les actifs et
        l’historique, sans retour.
      </p>

      {data.tenants.length === 0 ? (
        <p className="py-6 text-center text-sm text-ink-500">La corbeille est vide.</p>
      ) : (
        <ul className="space-y-2">
          {data.tenants.map((row) => (
            <li
              key={row.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-ink-200 px-3 py-2"
            >
              <span className="min-w-0">
                <span className="block truncate text-sm text-ink-800">{row.name}</span>
                <span className="text-xs text-ink-500">
                  Archivée il y a {row.days_since_archive} jour(s)
                  {row.archived_by && ` par ${row.archived_by}`}
                  {row.reason && ` — ${row.reason}`}
                </span>
              </span>
              <span className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={RotateCcw}
                  disabled={busy === row.id}
                  onClick={() => restore(row)}
                >
                  Restaurer
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  icon={Trash2}
                  disabled={busy === row.id || !row.purgeable}
                  title={
                    row.purgeable
                      ? undefined
                      : `Possible après ${data.retention_days} jours d’archivage.`
                  }
                  onClick={() => setDeleting(row)}
                >
                  Supprimer définitivement
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={destroy}
        danger
        title="Suppression définitive"
        summary={`Toutes les données de ${deleting?.name} seront détruites.`}
        consequences={[
          'Diagnostics, plans d’action, actifs, historique de fuites : tout disparaît.',
          'Aucune restauration ne sera possible.',
          'Les lignes du journal d’audit la concernant sont conservées.',
        ]}
        confirmText={deleting?.name}
        confirmLabel="Supprimer définitivement"
        loading={busy === deleting?.id}
      />
    </Card>
  )
}
