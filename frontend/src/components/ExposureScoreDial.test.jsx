import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ExposureScoreDial from './ExposureScoreDial'

// Le score est le chiffre qu'un client regarde en premier et qu'on montre en
// démonstration. Ce qui doit rester vrai : il s'affiche tel que le serveur
// l'a calculé (aucun arrondi ni recalcul côté client — ADR-016), et le cadran
// reste dans ses bornes même sur une valeur inattendue.

describe('ExposureScoreDial', () => {
  it('affiche le score et son niveau tels que renvoyés par le serveur', () => {
    render(<ExposureScoreDial score={78} level="critique" levelLabel="Critique" />)

    expect(screen.getByText('78')).toBeInTheDocument()
    expect(screen.getByText('Critique')).toBeInTheDocument()
  })

  it('affiche un score nul sans le confondre avec une absence de donnée', () => {
    render(<ExposureScoreDial score={0} level="calme" levelLabel="Calme" />)

    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByText('Calme')).toBeInTheDocument()
  })

  it('ne recalcule ni ne réinterprète le niveau côté client', () => {
    // Les seuils vivent dans les settings Django (ADR-016) : si le frontend
    // décidait lui-même du niveau à partir du score, un ajustement de seuil
    // côté serveur ne se refléterait pas à l'écran.
    render(<ExposureScoreDial score={10} level="critique" levelLabel="Critique" />)

    expect(screen.getByText('Critique')).toBeInTheDocument()
  })

  it('borne le remplissage du cadran pour une valeur hors échelle', () => {
    const { container } = render(
      <ExposureScoreDial score={250} level="critique" levelLabel="Critique" />
    )

    const arc = container.querySelectorAll('circle')[1]
    const [filled] = arc.getAttribute('stroke-dasharray').split(' ').map(Number)
    const circumference = 2 * Math.PI * 20
    expect(filled).toBeLessThanOrEqual(circumference)
  })

  it('retombe sur un style neutre pour un niveau inconnu plutôt que de casser', () => {
    render(<ExposureScoreDial score={42} level="niveau-futur" levelLabel="Niveau futur" />)

    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('Niveau futur')).toBeInTheDocument()
  })
})
