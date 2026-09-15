import { Search } from 'lucide-react'

/**
 * Un champ de recherche, le même partout (lot C, point 22).
 *
 * Le libellé est obligatoire, même s'il n'est pas affiché : un champ sans nom
 * accessible s'annonce « zone d'édition » au lecteur d'écran, sans dire ce
 * qu'on y cherche.
 */
export default function SearchInput({ label, value, onChange, placeholder = 'Rechercher…', className = '' }) {
  if (!label) throw new Error('Un champ de recherche doit dire ce qu’il cherche.')
  return (
    <label className={`relative block min-w-0 ${className}`}>
      <span className="sr-only">{label}</span>
      <Search
        className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-500"
        aria-hidden="true"
      />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-ink-200 py-1.5 pl-8 pr-3 text-sm focus-visible:outline-2 focus-visible:outline-brand-600"
      />
    </label>
  )
}
