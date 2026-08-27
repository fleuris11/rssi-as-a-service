import { Loader2 } from 'lucide-react'

// L'action primaire est le BLEU DE MARQUE, plus l'ambre.
//
// L'ambre (`accent`) portait l'action primaire, et sa version foncée est
// à quelques degrés de `warning`. Sur la page Compromissions, cela donnait
// onze boutons ambre pleins — dix « Marquer traité » et « Lancer un scan » —
// au milieu d'encadrés « À faire » et de bandeaux d'alerte eux aussi ambre.
// La teinte censée dire « c'est ici qu'on agit » disait aussi « attention »,
// et à cette fréquence elle ne disait plus rien du tout.
//
// Passer l'action en bleu de marque libère tout le spectre chaud pour la
// seule échelle de gravité. L'ambre reste la couleur de la marque (logo,
// signature), jamais un signal.
//
// `disabled` : la couleur seule ne suffit pas à signaler l'indisponibilité —
// le curseur et l'attribut natif la portent aussi.
const VARIANTS = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-600/45',
  secondary:
    'bg-surface text-ink-700 border border-ink-200 hover:bg-ink-50 hover:border-ink-300 disabled:text-ink-400 disabled:hover:bg-surface',
  ghost: 'bg-transparent text-ink-600 hover:bg-ink-100 disabled:text-ink-300',
  danger: 'bg-critical-strong text-white hover:bg-critical-strong/90 disabled:bg-critical-strong/50',
}

const SIZES = {
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-4 py-2 text-sm gap-2',
}

export default function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  disabled = false,
  icon: Icon,
  className = '',
  children,
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={`transition-smooth inline-flex items-center justify-center rounded-md font-medium disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? (
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      ) : (
        Icon && <Icon className="size-4" aria-hidden="true" />
      )}
      {children}
    </button>
  )
}
