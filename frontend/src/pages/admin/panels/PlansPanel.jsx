import { Copy, Eye, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { platformApi } from '../../../api/endpoints'
import ConfirmDialog from '../../../components/admin/ConfirmDialog'
import Field from '../../../components/admin/Field'
import Badge from '../../../components/ui/Badge'
import Button from '../../../components/ui/Button'
import Card, { CardHeader } from '../../../components/ui/Card'
import Modal from '../../../components/ui/Modal'
import { useToast } from '../../../components/ui/Toast'

const STATUS_LABEL = { draft: 'Brouillon', published: 'Publiée', retired: 'Retirée' }
const STATUS_VARIANT = { draft: 'neutral', published: 'ok', retired: 'warning' }
const QUOTA_LABEL = {
  monitored_assets: 'emplacements surveillés',
  monthly_scans: 'analyses par mois',
  max_users: 'utilisateurs',
}

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

const EMPTY_PLAN = {
  code: '',
  name: '',
  tagline: '',
  description: '',
  price_monthly: '0',
  price_yearly: '0',
  currency: 'EUR',
  is_quote_only: false,
  status: 'draft',
  display_order: 10,
  is_highlighted: false,
  monitored_assets: 1,
  monthly_scans: 20,
  max_users: 3,
  features: [],
}

function PlanEditor({ open, onClose, plan, featureCatalog, onSaved }) {
  const { showToast } = useToast()
  const [form, setForm] = useState(EMPTY_PLAN)
  const [impact, setImpact] = useState(null)
  const [saving, setSaving] = useState(false)
  const isNew = !plan

  useEffect(() => {
    if (!open) return
    setImpact(null)
    setForm(plan ? { ...EMPTY_PLAN, ...plan, features: plan.features || [] } : EMPTY_PLAN)
  }, [open, plan])

  function update(name, value) {
    setForm((previous) => ({ ...previous, [name]: value }))
  }

  function toggleFeature(key) {
    setForm((previous) => ({
      ...previous,
      features: previous.features.includes(key)
        ? previous.features.filter((f) => f !== key)
        : [...previous.features, key],
    }))
  }

  /** Aperçu AVANT écriture : combien de clients, et ce qui change pour eux. */
  async function preview() {
    if (isNew) return submit(true)
    try {
      const response = await platformApi.planImpact(plan.code, {
        monitored_assets: Number(form.monitored_assets),
        monthly_scans: Number(form.monthly_scans),
        max_users: Number(form.max_users),
      })
      if (response.data.subscriber_count === 0 || !response.data.will_freeze_existing) {
        return submit(true)
      }
      setImpact(response.data)
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'Aperçu indisponible.') })
    }
  }

  async function submit(skipConfirm = false) {
    if (!skipConfirm && impact) return
    setSaving(true)
    try {
      const payload = {
        ...form,
        display_order: Number(form.display_order),
        monitored_assets: Number(form.monitored_assets),
        monthly_scans: Number(form.monthly_scans),
        max_users: Number(form.max_users),
      }
      if (isNew) {
        await platformApi.createPlan(payload)
        showToast({ type: 'success', message: 'Offre créée en brouillon.' })
      } else {
        const response = await platformApi.updatePlan(plan.code, payload)
        const frozen = response.data.frozen_tenants || []
        showToast({
          type: 'success',
          message: frozen.length
            ? `Offre modifiée. Quota figé pour ${frozen.length} client(s) existant(s).`
            : 'Offre modifiée.',
        })
      }
      onSaved()
      onClose()
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'L’enregistrement a échoué.') })
    } finally {
      setSaving(false)
      setImpact(null)
    }
  }

  return (
    <>
      <Modal
        open={open && !impact}
        onClose={onClose}
        title={isNew ? 'Nouvelle offre' : `Modifier « ${plan?.name} »`}
        className="max-w-3xl"
      >
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault()
            preview()
          }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Code"
              name="code"
              value={form.code}
              onChange={update}
              required
              disabled={!isNew}
              hint={isNew ? 'Identifiant technique, non modifiable ensuite.' : 'Non modifiable.'}
            />
            <Field label="Nom affiché" name="name" value={form.name} onChange={update} required />
          </div>
          <Field label="Accroche" name="tagline" value={form.tagline} onChange={update} />
          <Field
            label="Descriptif"
            name="description"
            type="textarea"
            value={form.description}
            onChange={update}
          />

          <div className="grid gap-4 sm:grid-cols-4">
            <Field label="Prix mensuel" name="price_monthly" type="number" value={form.price_monthly} onChange={update} />
            <Field label="Prix annuel" name="price_yearly" type="number" value={form.price_yearly} onChange={update} />
            <Field label="Devise" name="currency" value={form.currency} onChange={update} />
            <Field label="Ordre d’affichage" name="display_order" type="number" value={form.display_order} onChange={update} />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field
              label="Emplacements surveillés"
              name="monitored_assets"
              type="number"
              value={form.monitored_assets}
              onChange={update}
              hint="Compte dans le pool partagé de la plateforme."
            />
            <Field label="Analyses par mois" name="monthly_scans" type="number" value={form.monthly_scans} onChange={update} hint="0 = illimité" />
            <Field label="Utilisateurs" name="max_users" type="number" value={form.max_users} onChange={update} hint="0 = illimité" />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field
              label="État"
              name="status"
              value={form.status}
              onChange={update}
              options={[
                { value: 'draft', label: 'Brouillon (invisible)' },
                { value: 'published', label: 'Publiée (sur la vitrine)' },
                { value: 'retired', label: 'Retirée de la vente' },
              ]}
            />
            <Field label="Sur devis" name="is_quote_only" type="checkbox" value={form.is_quote_only} onChange={update} />
            <Field label="Mise en avant" name="is_highlighted" type="checkbox" value={form.is_highlighted} onChange={update} />
          </div>

          <fieldset>
            <legend className="text-sm font-medium text-ink-700">Fonctionnalités comprises</legend>
            <p className="mb-2 mt-1 text-xs text-ink-500">
              Cette liste est déclarée dans le code : une fonctionnalité n’apparaît ici que si le
              produit sait réellement la rendre.
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {featureCatalog.map((feature) => (
                <label key={feature.key} className="flex items-start gap-2 text-sm text-ink-700">
                  <input
                    type="checkbox"
                    checked={form.features.includes(feature.key)}
                    onChange={() => toggleFeature(feature.key)}
                    className="mt-0.5 size-4 rounded border-ink-300 text-brand-700"
                  />
                  {feature.label}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="flex justify-end gap-2">
            <Button variant="ghost" type="button" onClick={onClose} disabled={saving}>
              Annuler
            </Button>
            <Button type="submit" loading={saving}>
              {isNew ? 'Créer l’offre' : 'Enregistrer'}
            </Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(impact)}
        onClose={() => setImpact(null)}
        onConfirm={() => submit(true)}
        title="Cette modification baisse un quota"
        summary={`${impact?.subscriber_count} client(s) sont actuellement sur cette offre.`}
        consequences={[
          `Quota(s) concerné(s) : ${(impact?.lowered_quotas || [])
            .map((q) => QUOTA_LABEL[q] || q)
            .join(', ')}.`,
          'Les clients existants CONSERVENT leur quota actuel : une surcharge le fige pour chacun.',
          'Le nouveau quota ne s’appliquera qu’aux clients créés après cette modification.',
          'Vous pourrez lever ce gel client par client depuis leur fiche.',
        ]}
        confirmLabel="Appliquer"
        loading={saving}
      />
    </>
  )
}

function PlanPreview({ code, onClose }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!code) return
    platformApi.previewPlan(code).then((response) => setData(response.data))
  }, [code])

  return (
    <Modal open={Boolean(code)} onClose={onClose} title="Aperçu vitrine">
      {data && (
        <div className="space-y-4">
          {!data.is_visible_publicly && (
            <p className="rounded-md border border-warning-200 bg-warning-50 px-3 py-2 text-sm text-ink-700">
              Cette offre n’est pas publiée : elle n’apparaît pas sur le site public. L’aperçu
              montre ce que verraient les visiteurs une fois publiée.
            </p>
          )}
          <div className="rounded-lg border border-ink-200 p-5">
            <p className="font-display text-lg font-semibold text-ink-900">{data.plan.name}</p>
            <p className="mt-1 text-sm text-ink-600">{data.plan.tagline}</p>
            <p className="mt-3 font-display text-2xl font-semibold text-ink-900">
              {data.plan.is_quote_only ? 'Sur devis' : `${Number(data.plan.price_monthly)} €`}
              {!data.plan.is_quote_only && (
                <span className="text-sm font-normal text-ink-500"> / mois</span>
              )}
            </p>
            <ul className="mt-4 space-y-1.5">
              {(data.plan.features || []).map((feature) => (
                <li key={feature.key} className="text-sm text-ink-700">
                  — {feature.label}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Modal>
  )
}

export default function PlansPanel({ plans, featureCatalog, onRefresh }) {
  const { showToast } = useToast()
  const [editing, setEditing] = useState(undefined)
  const [previewing, setPreviewing] = useState(null)
  const [duplicating, setDuplicating] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [duplicateForm, setDuplicateForm] = useState({ code: '', name: '' })
  const [busy, setBusy] = useState(false)

  async function confirmDuplicate() {
    setBusy(true)
    try {
      await platformApi.duplicatePlan(duplicating.code, duplicateForm)
      setDuplicating(null)
      onRefresh()
      showToast({ type: 'success', message: 'Copie créée en brouillon.' })
    } catch (error) {
      showToast({ type: 'error', message: serverMessage(error, 'La duplication a échoué.') })
    } finally {
      setBusy(false)
    }
  }

  async function confirmDelete() {
    setBusy(true)
    try {
      await platformApi.deletePlan(deleting.code)
      setDeleting(null)
      onRefresh()
      showToast({ type: 'success', message: 'Offre supprimée.' })
    } catch (error) {
      // Le serveur explique pourquoi une offre utilisée ne peut pas être
      // supprimée, et ce qu'il faut faire à la place.
      showToast({ type: 'error', message: serverMessage(error, 'La suppression a échoué.') })
      setDeleting(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title="Offres"
        action={
          <Button icon={Plus} size="sm" onClick={() => setEditing(null)}>
            Nouvelle offre
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-600">
        Les offres publiées alimentent la grille tarifaire du site public. Une offre utilisée par
        des clients ne peut pas être supprimée : elle se retire de la vente et reste valable pour
        eux.
      </p>

      <div className="space-y-3">
        {plans.map((plan) => (
          <div key={plan.code} className="rounded-lg border border-ink-200 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2 font-medium text-ink-900">
                  {plan.name}
                  <Badge variant={STATUS_VARIANT[plan.status] || 'neutral'}>
                    {STATUS_LABEL[plan.status] || plan.status}
                  </Badge>
                  {plan.is_highlighted && <Badge variant="brand">Mise en avant</Badge>}
                </p>
                <p className="mt-1 text-sm text-ink-600">
                  {plan.is_quote_only ? 'Sur devis' : `${Number(plan.price_monthly)} € / mois`} ·{' '}
                  {plan.monitored_assets} emplacement(s) · {plan.monthly_scans || '∞'} analyse(s) ·{' '}
                  {plan.max_users || '∞'} utilisateur(s)
                </p>
                <p className="mt-1 text-xs text-ink-500">
                  {(plan.feature_labels || []).join(' · ') || 'Aucune fonctionnalité cochée'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="ghost" size="sm" icon={Eye} onClick={() => setPreviewing(plan.code)}>
                  Aperçu
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={Copy}
                  onClick={() => {
                    setDuplicating(plan)
                    setDuplicateForm({ code: `${plan.code}-copie`, name: `${plan.name} (copie)` })
                  }}
                >
                  Dupliquer
                </Button>
                <Button variant="secondary" size="sm" onClick={() => setEditing(plan)}>
                  Modifier
                </Button>
                <Button variant="danger" size="sm" icon={Trash2} onClick={() => setDeleting(plan)}>
                  Supprimer
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <PlanEditor
        open={editing !== undefined}
        plan={editing}
        featureCatalog={featureCatalog}
        onClose={() => setEditing(undefined)}
        onSaved={onRefresh}
      />
      <PlanPreview code={previewing} onClose={() => setPreviewing(null)} />

      <Modal
        open={Boolean(duplicating)}
        onClose={() => setDuplicating(null)}
        title={`Dupliquer « ${duplicating?.name} »`}
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-600">
            La copie est créée en brouillon, sans mise en avant : elle n’apparaîtra sur la vitrine
            qu’une fois relue et publiée.
          </p>
          <Field
            label="Code de la copie"
            name="code"
            value={duplicateForm.code}
            onChange={(name, value) => setDuplicateForm((p) => ({ ...p, [name]: value }))}
            required
          />
          <Field
            label="Nom de la copie"
            name="name"
            value={duplicateForm.name}
            onChange={(name, value) => setDuplicateForm((p) => ({ ...p, [name]: value }))}
            required
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDuplicating(null)}>
              Annuler
            </Button>
            <Button onClick={confirmDuplicate} loading={busy}>
              Dupliquer
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={confirmDelete}
        danger
        title={`Supprimer « ${deleting?.name} » ?`}
        summary="La suppression n’est possible que si aucun client n’est sur cette offre."
        consequences={[
          'Si des clients y sont abonnés, l’opération sera refusée avec le nombre exact.',
          'Dans ce cas, retirez l’offre de la vente : elle disparaît de la vitrine et reste valable pour ses clients.',
        ]}
        confirmLabel="Supprimer"
        loading={busy}
      />
    </Card>
  )
}
