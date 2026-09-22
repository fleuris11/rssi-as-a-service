import { Link } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'

/**
 * MOT DE PASSE OUBLIÉ.
 *
 * **Il n'y a pas de formulaire ici, et c'est délibéré.** Le backend n'expose
 * aucune route de réinitialisation : `apps/accounts/urls.py` ne connaît que
 * la connexion, le rafraîchissement de jeton, la double authentification et
 * l'acceptation d'invitation. Poser un champ « votre email » qui n'enverrait
 * rien serait pire que l'absence de page — la personne attendrait un courriel
 * qui ne partirait jamais, et recommencerait.
 *
 * Cette page dit donc la procédure RÉELLE : un administrateur de l'espace
 * réémet une invitation, laquelle permet de reposer un mot de passe. C'est le
 * seul chemin qui existe aujourd'hui.
 *
 * À FAIRE (hors périmètre de la refonte, qui ne touche pas au backend) :
 * une route de réinitialisation par jeton à usage unique, avec la même
 * discipline que l'invitation — jeton haché en base, valeur en clair une
 * seule fois, expiration courte.
 */
export default function MotDePasseOubliePage() {
  return (
    <AuthLayout>
      <h1 className="t-display">Mot de passe oublié</h1>
      <p className="t-body mt-3">
        Il n’existe pas encore de réinitialisation automatique par courriel. Voici ce qui
        fonctionne aujourd’hui, dans l’ordre.
      </p>

      <ol className="mt-6">
        <li className="ligne-liste py-4 first:pt-0">
          <p className="text-sm font-semibold text-ink-900">
            Demandez une nouvelle invitation à un administrateur de votre espace
          </p>
          <p className="t-body mt-1">
            Depuis <span className="font-medium">Préférences</span>, un administrateur peut vous
            réinviter. Vous recevez un lien personnel qui vous fait choisir un nouveau mot de
            passe.
          </p>
        </li>
        <li className="ligne-liste py-4">
          <p className="text-sm font-semibold text-ink-900">
            Vous êtes seul administrateur, ou personne ne répond
          </p>
          <p className="t-body mt-1">
            Écrivez à{' '}
            <a
              href="mailto:contact@rssiasservice.online"
              className="n text-brand-600 underline underline-offset-4"
            >
              contact@rssiasservice.online
            </a>{' '}
            depuis l’adresse du compte concerné. Nous vérifions puis réémettons l’invitation.
          </p>
        </li>
        <li className="ligne-liste py-4">
          <p className="text-sm font-semibold text-ink-900">
            Vous avez perdu votre second facteur, pas votre mot de passe
          </p>
          <p className="t-body mt-1">
            Utilisez l’un des codes de récupération notés lors de l’activation : sur l’écran de
            vérification, choisissez « Utiliser un code de récupération ». Chacun ne sert qu’une
            fois.
          </p>
        </li>
      </ol>

      <p className="mt-6 border-t border-ink-200 pt-5 text-sm">
        <Link to="/connexion" className="text-brand-600 underline underline-offset-4">
          Revenir à la connexion
        </Link>
      </p>
    </AuthLayout>
  )
}
