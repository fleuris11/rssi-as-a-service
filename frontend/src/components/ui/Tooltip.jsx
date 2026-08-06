import { cloneElement, useId } from 'react'

export default function Tooltip({ label, children, side = 'top' }) {
  const id = useId()
  const positionClass =
    side === 'top'
      ? 'bottom-full left-1/2 mb-2 -translate-x-1/2'
      : 'top-full left-1/2 mt-2 -translate-x-1/2'

  return (
    <span className="group relative inline-flex">
      {cloneElement(children, { 'aria-describedby': id })}
      <span
        role="tooltip"
        id={id}
        className={`transition-smooth pointer-events-none absolute z-50 whitespace-nowrap rounded-md bg-ink-900 px-2 py-1 text-xs text-white opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 ${positionClass}`}
      >
        {label}
      </span>
    </span>
  )
}
