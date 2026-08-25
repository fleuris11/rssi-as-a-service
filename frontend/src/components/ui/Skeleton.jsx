export default function Skeleton({ className = '' }) {
  return (
    // `data-loading` : repère stable pour les tests de bout en bout, qui
    // attendent la fin du chargement plutôt qu'un délai arbitraire.
    <div
      className={`animate-pulse rounded-md bg-ink-200/70 ${className}`}
      aria-hidden="true"
      data-loading="true"
    />
  )
}

export function SkeletonText({ lines = 3, className = '' }) {
  return (
    <div className={`space-y-2 ${className}`} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={`h-3 ${i === lines - 1 ? 'w-2/3' : 'w-full'}`} />
      ))}
    </div>
  )
}

export function SkeletonCard({ className = '' }) {
  return (
    <div className={`rounded-lg border border-ink-200/70 bg-surface p-6 ${className}`}>
      <Skeleton className="mb-4 h-4 w-1/3" />
      <SkeletonText lines={2} />
    </div>
  )
}
