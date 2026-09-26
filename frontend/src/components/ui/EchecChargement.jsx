import Button from './Button'

/**
 * UN ÉCHEC DE CHARGEMENT QUI SE VOIT ET SE RATTRAPE.
 *
 * Le motif `if (!donnees) return <SkeletonCard />` se lit bien, et il est
 * faux : quand l'appel échoue, `donnees` reste nul et **le squelette reste à
 * l'écran pour toujours**. La notification d'erreur, elle, s'efface au bout
 * de quelques secondes. L'exploitant se retrouve donc devant une animation de
 * chargement éternelle, sans savoir que rien ne viendra ni comment réessayer.
 *
 * Trouvé par un test e2e de la console qui attendait une liste de prospects
 * devant un squelette figé — pas à l'œil, parce qu'à l'œil un squelette
 * ressemble à de la patience.
 */
export default function EchecChargement({
  message = 'Ces données n’ont pas pu être chargées.',
  precision,
  onReessayer,
}) {
  return (
    <div className="panneau p-6" role="alert">
      <p className="flex items-start gap-2 text-sm font-semibold text-ink-900">
        <span aria-hidden="true" className="text-critical-strong">
          ▲
        </span>
        {message}
      </p>
      {precision && <p className="t-body mt-2">{precision}</p>}
      {onReessayer && (
        <Button className="mt-4" onClick={onReessayer}>
          Réessayer
        </Button>
      )}
    </div>
  )
}
