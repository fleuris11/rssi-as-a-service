export default function SegmentedControl({ options, value, onChange, disabled = false, className = '' }) {
  return (
    <div role="radiogroup" className={`inline-flex overflow-hidden rounded-md border border-ink-200 ${className}`}>
      {options.map((option, index) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={`transition-smooth px-3 py-1.5 text-sm font-medium outline-2 outline-offset-[-2px] focus-visible:outline disabled:cursor-not-allowed disabled:opacity-50 ${
              index > 0 ? 'border-l border-ink-200' : ''
            } ${selected ? 'bg-brand-700 text-white outline-white' : 'bg-surface text-ink-600 outline-brand-600 hover:bg-ink-50'}`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
