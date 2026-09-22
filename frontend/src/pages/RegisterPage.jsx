import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import Button from '../components/ui/Button'
import Champ from '../components/ui/Champ'
import { useAuth } from '../context/AuthContext'

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
      <h1 className="t-display">Créer votre espace entreprise</h1>
      <p className="t-meta mt-2">Vous en serez l’administrateur.</p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <Champ
          label="Nom de l’entreprise"
          required
          autoComplete="organization"
          value={form.company_name}
          onChange={updateField('company_name')}
        />
        <div className="grid grid-cols-2 gap-3">
          <Champ
            label="Prénom"
            autoComplete="given-name"
            value={form.first_name}
            onChange={updateField('first_name')}
          />
          <Champ
            label="Nom"
            autoComplete="family-name"
            value={form.last_name}
            onChange={updateField('last_name')}
          />
        </div>
        <Champ
          label="Email"
          type="email"
          required
          autoComplete="email"
          value={form.email}
          onChange={updateField('email')}
        />
        <Champ
          label="Mot de passe"
          type="password"
          required
          minLength={12}
          autoComplete="new-password"
          // L'aide est AU-DESSUS du champ : une contrainte lue après coup est
          // une contrainte découverte trop tard, une fois le mot de passe
          // déjà choisi et refusé.
          aide="12 caractères minimum."
          value={form.password}
          onChange={updateField('password')}
        />
        {errors.length > 0 && (
          <ul
            className="space-y-1 rounded-md bg-critical-subtle px-3 py-2 text-sm text-critical-strong"
            role="alert"
          >
            {errors.map((message) => (
              <li key={message} className="flex items-start gap-1.5">
                <span aria-hidden="true">▲</span>
                {message}
              </li>
            ))}
          </ul>
        )}
        <Button type="submit" variant="primary" loading={submitting} className="w-full">
          Créer mon compte
        </Button>
      </form>
      <p className="mt-6 border-t border-ink-200 pt-5 text-sm text-ink-600">
        Déjà un compte ?{' '}
        <Link to="/connexion" className="text-brand-600 underline underline-offset-4">
          Se connecter
        </Link>
      </p>
    </AuthLayout>
  )
}
