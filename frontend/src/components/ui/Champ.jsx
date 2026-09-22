import { useId } from 'react'

/**
 * UN CHAMP DE SAISIE, avec tous ses états.
 *
 * Trois règles, et chacune corrige un défaut courant :
 *
 * 1. **Le libellé est visible, toujours.** Un libellé en texte d'invite
 *    disparaît dès qu'on commence à taper : la personne ne sait plus ce
 *    qu'elle est en train de remplir, et ne peut pas relire son formulaire
 *    avant envoi.
 * 2. **L'erreur est au champ, pas en tête de page.** Un récapitulatif en haut
 *    oblige à faire l'aller-retour ; l'erreur au champ se lit là où on la
 *    corrige. `aria-describedby` la relie, `aria-invalid` la nomme.
 * 3. **L'aide est au-dessus de la saisie, pas en dessous.** Une contrainte
 *    lue après coup est une contrainte découverte trop tard.
 */
export default function Champ({
  label,
  aide,
  erreur,
  type = 'text',
  className = '',
  children,
  ...reste
}) {
  const identifiant = useId()
  const idAide = aide ? `${identifiant}-aide` : undefined
  const idErreur = erreur ? `${identifiant}-erreur` : undefined

  return (
    <div className={className}>
      <label htmlFor={identifiant} className="block text-sm font-semibold text-ink-800">
        {label}
      </label>
      {aide && (
        <p id={idAide} className="t-meta mt-0.5">
          {aide}
        </p>
      )}
      {children ? (
        children({ id: identifiant, describedBy: [idAide, idErreur].filter(Boolean).join(' ') })
      ) : (
        <input
          id={identifiant}
          type={type}
          aria-invalid={erreur ? 'true' : undefined}
          aria-describedby={[idAide, idErreur].filter(Boolean).join(' ') || undefined}
          className={`transition-smooth mt-1.5 w-full rounded-md border bg-surface px-3 py-2 text-sm text-ink-900 placeholder:text-ink-500 disabled:bg-creuse disabled:text-ink-500 ${
            erreur ? 'border-critical-strong' : 'border-ink-300 hover:border-ink-400'
          }`}
          {...reste}
        />
      )}
      {erreur && (
        <p id={idErreur} className="mt-1.5 flex items-start gap-1.5 text-sm text-critical-strong">
          {/* Le glyphe double la couleur : une erreur signalée par la seule
              teinte du filet n'existe pas pour qui ne la distingue pas. */}
          <span aria-hidden="true">▲</span>
          {erreur}
        </p>
      )}
    </div>
  )
}
