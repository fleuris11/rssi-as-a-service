import { Loader2 } from 'lucide-react'

// UNE SEULE COULEUR D'ACTION, et elle n'est jamais un état.
//
// L'ambre portait l'action primaire, et sa version foncée était à quelques
// degrés de « attention ». Sur la page Compromissions, cela donnait onze
// boutons ambre pleins au milieu d'encadrés et de bandeaux eux aussi ambre :
// la teinte censée dire « c'est ici qu'on agit » disait aussi « danger », et à
// cette fréquence elle ne disait plus rien.
//
// Tout le spectre chaud est donc rendu à la seule échelle de risque. L'action
// prend le bleu, qui n'est aucun des quatre crans.
//
// `disabled` : la couleur seule ne suffit pas à signaler l'indisponibilité —
// le curseur et l'attribut natif la portent aussi.
const VARIANTS = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-600/45',
  secondary:
    'bg-surface text-ink-800 border border-ink-300 hover:border-ink-400 hover:bg-creuse disabled:text-ink-400 disabled:hover:bg-surface',
  ghost: 'bg-transparent text-ink-600 hover:bg-creuse disabled:text-ink-300',
  danger:
    'bg-critical-strong text-white hover:brightness-95 disabled:bg-critical-strong/50',
}

const SIZES = {
  sm: 'px-2.5 py-1 text-xs gap-1.5',
  md: 'px-3.5 py-2 text-sm gap-2',
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
      className={`transition-smooth inline-flex items-center justify-center rounded-md font-semibold disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
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
