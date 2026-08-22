const baseInput =
  'transition-smooth mt-1 w-full rounded-md border border-ink-200 px-3 py-2 text-sm ' +
  'focus-visible:outline-2 focus-visible:outline-brand-600 disabled:bg-ink-50 disabled:text-ink-500'

/**
 * Champ de formulaire de la console.
 *
 * L'erreur est rendue sous le champ ET reliée par ``aria-describedby`` : un
 * message rouge qu'un lecteur d'écran n'annonce pas n'existe pas pour la
 * personne qui en a le plus besoin.
 */
export default function Field({
  label,
  name,
  value,
  onChange,
  type = 'text',
  options,
  error = '',
  hint = '',
  required = false,
  disabled = false,
  rows = 3,
  ...rest
}) {
  const id = `field-${name}`
  const describedBy = [error && `${id}-error`, hint && `${id}-hint`].filter(Boolean).join(' ')

  const common = {
    id,
    name,
    value: value ?? '',
    onChange: (event) => onChange(name, event.target.value),
    disabled,
    // ``required`` est porté par le champ lui-même, pas seulement par une
    // étoile dans le libellé : c'est ce que lisent les technologies
    // d'assistance. Les formulaires de la console portent ``noValidate`` :
    // sans lui, la validation native du navigateur bloque l'envoi AVANT la
    // nôtre, et l'utilisateur reçoit une bulle générique à la place d'un
    // message précis, aligné sur celui que renverrait le serveur.
    required,
    'aria-invalid': error ? 'true' : undefined,
    'aria-describedby': describedBy || undefined,
    className: `${baseInput} ${error ? 'border-critical-strong' : ''}`,
    ...rest,
  }

  return (
    <div>
      <label className="block text-sm font-medium text-ink-700" htmlFor={id}>
        {label}
        {/* Marqueur visuel uniquement : l'astérisque ne doit pas entrer dans
            le nom accessible du champ (« Email * » au lieu de « Email »),
            sinon il brouille aussi bien les lecteurs d'écran que les
            recherches par libellé. */}
        {required && (
          <span className="text-critical-strong" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </label>

      {options ? (
        <select {...common}>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : type === 'textarea' ? (
        <textarea {...common} rows={rows} />
      ) : type === 'checkbox' ? (
        <input
          id={id}
          name={name}
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(name, event.target.checked)}
          disabled={disabled}
          className="mt-2 size-4 rounded border-ink-300 text-brand-700 focus-visible:outline-2 focus-visible:outline-brand-600"
        />
      ) : (
        <input {...common} type={type} />
      )}

      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-ink-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1 text-xs text-critical-strong">
          {error}
        </p>
      )}
    </div>
  )
}
