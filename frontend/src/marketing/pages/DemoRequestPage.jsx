import { Check } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { publicApi } from '../../api/endpoints'
import MarketingLayout from '../components/MarketingLayout'
import { COMPANY_SIZES, DEMO_FORM, SLOTS } from '../content'
import { useSeo } from '../useSeo'

const EMPTY = {
  full_name: '',
  company: '',
  role: '',
  email: '',
  company_size: '',
  preferred_slot: '',
  message: '',
  website: '', // honeypot
}

function Field({ label, name, children, error, required }) {
  return (
    <div>
      <label htmlFor={name} className="block text-sm font-medium text-ink-800">
        {label}
        {required && <span className="text-critical-strong"> *</span>}
      </label>
      <div className="mt-1.5">{children}</div>
      {error && (
        <p id={`${name}-error`} className="mt-1.5 text-sm text-critical-strong">
          {error}
        </p>
      )}
    </div>
  )
}

const inputClass =
  'w-full rounded-md border border-ink-300 px-3 py-2.5 text-sm text-ink-900 outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-600'

export default function DemoRequestPage() {
  useSeo({
    title: 'Demander une démonstration',
    description:
      "Une démonstration d'une vingtaine de minutes, en partage d'écran, sans installation. Réponse sous un jour ouvré.",
    path: '/demonstration',
  })

  const [values, setValues] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  function update(name, value) {
    setValues((v) => ({ ...v, [name]: value }))
    setErrors((e) => (e[name] ? { ...e, [name]: undefined } : e))
  }

  function validate() {
    const next = {}
    if (values.full_name.trim().length < 2) next.full_name = 'Merci d’indiquer votre nom.'
    if (values.company.trim().length < 2) next.company = 'Merci d’indiquer votre société.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) {
      next.email = 'Merci d’indiquer une adresse email valide.'
    }
    return next
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (submitting) return

    const clientErrors = validate()
    if (Object.keys(clientErrors).length > 0) {
      setErrors(clientErrors)
      return
    }

    setSubmitting(true)
    try {
      await publicApi.requestDemo(values)
      setDone(true)
    } catch (err) {
      const data = err.response?.data
      if (err.response?.status === 429) {
        setErrors({ detail: 'Trop de demandes envoyées. Réessayez dans un moment.' })
      } else if (data && typeof data === 'object') {
        // Les erreurs de champ renvoyées par le serveur arrivent sous forme
        // de listes : on n'affiche que la première, la plus lisible.
        const mapped = Object.fromEntries(
          Object.entries(data).map(([key, value]) => [
            key,
            Array.isArray(value) ? value[0] : String(value),
          ])
        )
        setErrors(mapped)
      } else {
        setErrors({ detail: 'Votre demande n’a pas pu être envoyée. Réessayez.' })
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <MarketingLayout>
        <div className="mx-auto max-w-2xl px-5 py-24">
          <div className="rounded-lg border border-ok-strong/30 bg-ok-subtle p-8">
            <span
              aria-hidden="true"
              className="flex size-11 items-center justify-center rounded-full bg-ok-strong/15 text-ok-strong"
            >
              <Check className="size-6" />
            </span>
            <h1 className="mt-5 font-display text-2xl font-semibold text-ink-900">
              {DEMO_FORM.successTitle}
            </h1>
            <p className="mt-3 text-base leading-relaxed text-ink-700">{DEMO_FORM.successBody}</p>
            <Link
              to="/"
              className="transition-smooth mt-7 inline-block rounded-md border border-ink-300 bg-surface px-5 py-2.5 text-sm font-medium text-ink-800 hover:bg-ink-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
            >
              Revenir à l’accueil
            </Link>
          </div>
        </div>
      </MarketingLayout>
    )
  }

  return (
    <MarketingLayout>
      <div className="mx-auto max-w-2xl px-5 py-16 sm:py-20">
        <h1 className="font-display text-3xl font-semibold text-ink-900">{DEMO_FORM.title}</h1>
        <p className="mt-3 text-base leading-relaxed text-ink-600">{DEMO_FORM.subtitle}</p>

        <form onSubmit={handleSubmit} noValidate className="mt-10 space-y-5">
          {errors.detail && (
            <p role="alert" className="rounded-md bg-critical-subtle px-4 py-3 text-sm text-critical-strong">
              {errors.detail}
            </p>
          )}

          <div className="grid gap-5 sm:grid-cols-2">
            <Field label={DEMO_FORM.fields.fullName} name="full_name" error={errors.full_name} required>
              <input
                id="full_name"
                name="full_name"
                type="text"
                autoComplete="name"
                value={values.full_name}
                onChange={(e) => update('full_name', e.target.value)}
                aria-invalid={Boolean(errors.full_name)}
                aria-describedby={errors.full_name ? 'full_name-error' : undefined}
                className={inputClass}
              />
            </Field>

            <Field label={DEMO_FORM.fields.company} name="company" error={errors.company} required>
              <input
                id="company"
                name="company"
                type="text"
                autoComplete="organization"
                value={values.company}
                onChange={(e) => update('company', e.target.value)}
                aria-invalid={Boolean(errors.company)}
                aria-describedby={errors.company ? 'company-error' : undefined}
                className={inputClass}
              />
            </Field>

            <Field label={DEMO_FORM.fields.role} name="role" error={errors.role}>
              <input
                id="role"
                name="role"
                type="text"
                autoComplete="organization-title"
                value={values.role}
                onChange={(e) => update('role', e.target.value)}
                className={inputClass}
              />
            </Field>

            <Field label={DEMO_FORM.fields.email} name="email" error={errors.email} required>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                value={values.email}
                onChange={(e) => update('email', e.target.value)}
                aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email ? 'email-error' : undefined}
                className={inputClass}
              />
            </Field>

            <Field label={DEMO_FORM.fields.companySize} name="company_size">
              <select
                id="company_size"
                name="company_size"
                value={values.company_size}
                onChange={(e) => update('company_size', e.target.value)}
                className={inputClass}
              >
                <option value="">Non précisé</option>
                {COMPANY_SIZES.map((size) => (
                  <option key={size.value} value={size.value}>
                    {size.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label={DEMO_FORM.fields.preferredSlot} name="preferred_slot">
              <select
                id="preferred_slot"
                name="preferred_slot"
                value={values.preferred_slot}
                onChange={(e) => update('preferred_slot', e.target.value)}
                className={inputClass}
              >
                <option value="">Non précisé</option>
                {SLOTS.map((slot) => (
                  <option key={slot.value} value={slot.value}>
                    {slot.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label={DEMO_FORM.fields.message} name="message" error={errors.message}>
            <textarea
              id="message"
              name="message"
              rows={4}
              value={values.message}
              onChange={(e) => update('message', e.target.value)}
              placeholder={DEMO_FORM.messagePlaceholder}
              className={inputClass}
            />
          </Field>

          {/* Honeypot : masqué visuellement ET retiré de l'ordre de
              tabulation et de l'arbre d'accessibilité, pour qu'aucun humain
              — y compris au lecteur d'écran — ne le rencontre jamais. */}
          <div aria-hidden="true" className="absolute left-[-9999px] h-px w-px overflow-hidden">
            <label htmlFor="website">Ne pas remplir</label>
            <input
              id="website"
              name="website"
              type="text"
              tabIndex={-1}
              autoComplete="off"
              value={values.website}
              onChange={(e) => update('website', e.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="transition-smooth rounded-md bg-brand-700 px-5 py-3 text-sm font-medium text-white hover:bg-brand-800 disabled:cursor-not-allowed disabled:bg-ink-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
            >
              {submitting ? DEMO_FORM.submitting : DEMO_FORM.submit}
            </button>
            <p className="text-xs text-ink-500">* Champs obligatoires</p>
          </div>

          <p className="text-xs leading-relaxed text-ink-500">{DEMO_FORM.privacyNote}</p>
        </form>
      </div>
    </MarketingLayout>
  )
}
