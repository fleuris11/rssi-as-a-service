const VARIANTS = {
  ok: 'bg-ok-subtle text-ok-strong',
  warning: 'bg-warning-subtle text-warning-strong',
  critical: 'bg-critical-subtle text-critical-strong',
  neutral: 'bg-ink-100 text-ink-700',
  accent: 'bg-accent-100 text-accent-900',
  brand: 'bg-brand-100 text-brand-800',
}

const DOT_COLOR = {
  ok: 'bg-ok-strong',
  warning: 'bg-warning-strong',
  critical: 'bg-critical-strong',
  neutral: 'bg-ink-500',
  accent: 'bg-accent-600',
  brand: 'bg-brand-600',
}

export default function Badge({ variant = 'neutral', dot = false, className = '', children }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${VARIANTS[variant]} ${className}`}
    >
      {dot && <span className={`size-1.5 rounded-full ${DOT_COLOR[variant]}`} aria-hidden="true" />}
      {children}
    </span>
  )
}
