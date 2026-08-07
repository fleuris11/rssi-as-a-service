import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import Button from '../components/ui/Button'
import { useAuth } from '../context/AuthContext'

const inputClass =
  'transition-smooth mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600'

const initialForm = {
  company_name: '',
  first_name: '',
  last_name: '',
  email: '',
  password: '',
}

function extractErrorMessages(data) {
  if (!data || typeof data !== 'object') return ['Une erreur est survenue.']
  return Object.values(data).flat().map(String)
}

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState([])
  const [submitting, setSubmitting] = useState(false)

  function updateField(field) {
    return (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setErrors([])
    setSubmitting(true)
    try {
      await register(form)
      navigate('/tableau-de-bord')
    } catch (error) {
      setErrors(extractErrorMessages(error.response?.data))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-semibold text-ink-900">
        Créer votre espace entreprise
      </h1>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-ink-700" htmlFor="company_name">
            Nom de l’entreprise
          </label>
          <input
            id="company_name"
            required
            value={form.company_name}
            onChange={updateField('company_name')}
            className={inputClass}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-ink-700" htmlFor="first_name">
              Prénom
            </label>
            <input
              id="first_name"
              value={form.first_name}
              onChange={updateField('first_name')}
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-700" htmlFor="last_name">
              Nom
            </label>
            <input
              id="last_name"
              value={form.last_name}
              onChange={updateField('last_name')}
              className={inputClass}
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-ink-700" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            value={form.email}
            onChange={updateField('email')}
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-ink-700" htmlFor="password">
            Mot de passe
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={12}
            value={form.password}
            onChange={updateField('password')}
            className={inputClass}
          />
          <p className="mt-1 text-xs text-ink-400">12 caractères minimum.</p>
        </div>
        {errors.length > 0 && (
          <ul className="space-y-1 text-sm text-critical-strong">
            {errors.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}
        <Button type="submit" variant="primary" loading={submitting} className="w-full">
          Créer mon compte
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-ink-500">
        Déjà un compte ?{' '}
        <Link to="/connexion" className="font-medium text-brand-700 underline">
          Se connecter
        </Link>
      </p>
    </AuthLayout>
  )
}
