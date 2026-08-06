import { Loader2 } from 'lucide-react'

const VARIANTS = {
  // Accent (amber) is reserved for the one true primary action on a
  // screen — "used sparingly" per the design brief, not a default.
  primary:
    'bg-accent-700 text-white hover:bg-accent-800 focus-visible:outline-accent-700 disabled:bg-accent-700/50',
  secondary:
    'bg-surface text-ink-700 border border-ink-200 hover:bg-ink-50 focus-visible:outline-brand-600 disabled:text-ink-400',
  ghost:
    'bg-transparent text-ink-600 hover:bg-ink-100 focus-visible:outline-brand-600 disabled:text-ink-300',
  danger:
    'bg-critical-strong text-white hover:bg-critical-strong/90 focus-visible:outline-critical-strong disabled:bg-critical-strong/50',
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
      className={`transition-smooth inline-flex items-center justify-center rounded-md font-medium outline-offset-2 focus-visible:outline-2 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
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
