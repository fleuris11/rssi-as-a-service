import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ScoreGauge from './ScoreGauge'

// Reprend les garanties de l'ancien `ExposureScoreDial` — le score s'affiche
// tel que le serveur l'a calculé (ADR-016), le cadran reste borné, un niveau
// inconnu ne casse rien — et y ajoute celle qui a motivé la fusion des deux
// jauges : une échelle dit dans quel sens elle se lit.

describe('ScoreGauge', () => {
  it('affiche le score et son niveau tels que renvoyés par le serveur', () => {
    render(<ScoreGauge score={78} level="critique" levelLabel="Critique" />)

    expect(screen.getByText('78')).toBeInTheDocument()
    expect(screen.getByText('Critique')).toBeInTheDocument()
  })

  it('affiche un score nul sans le confondre avec une absence de donnée', () => {
    render(<ScoreGauge score={0} level="calme" levelLabel="Calme" />)

    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByText('Calme')).toBeInTheDocument()
  })

  it('distingue un score absent d’un score nul', () => {
    render(<ScoreGauge score={null} scale="maturity" />)

    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.queryByText('0')).toBeNull()
  })

  it('ne recalcule ni ne réinterprète le niveau côté client', () => {
    // Les seuils vivent dans les settings Django (ADR-016) : si le frontend
    // décidait lui-même du niveau à partir du score, un ajustement de seuil
    // côté serveur ne se refléterait pas à l'écran.
    render(<ScoreGauge score={10} level="critique" levelLabel="Critique" />)

    expect(screen.getByText('Critique')).toBeInTheDocument()
  })

  it('borne le remplissage du cadran pour une valeur hors échelle', () => {
    const { container } = render(<ScoreGauge score={250} level="critique" levelLabel="Critique" />)

    const arc = container.querySelectorAll('circle')[1]
    const circonference = Number(arc.getAttribute('stroke-dasharray'))
    const reste = Number(arc.getAttribute('stroke-dashoffset'))
    // Borné à 100 % : il ne reste rien à remplir, et jamais une valeur
    // négative qui ferait déborder l'arc.
    expect(reste).toBe(0)
    expect(circonference).toBeGreaterThan(0)
  })

  it('retombe sur un rendu neutre pour un niveau inconnu plutôt que de casser', () => {
    render(<ScoreGauge score={42} level="niveau-futur" levelLabel="Niveau futur" />)

    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('Niveau futur')).toBeInTheDocument()
  })

  describe('sens de lecture', () => {
    // Le défaut que ce composant existe pour réparer : deux anneaux
    // identiques portaient des échelles inverses — 80 vert d'un côté,
    // 80 rouge de l'autre — sans que rien à l'écran ne le dise.

    it('dit qu’un score d’exposition élevé est un risque élevé', () => {
      render(<ScoreGauge score={80} scale="exposure" showLegend />)

      expect(screen.getByText(/plus le risque est élevé/)).toBeInTheDocument()
    })

    it('dit qu’un score de maturité élevé est une bonne nouvelle', () => {
      render(<ScoreGauge score={80} scale="maturity" showLegend />)

      expect(screen.getByText(/meilleure est la maturité/)).toBeInTheDocument()
    })

    it('donne au même chiffre deux niveaux opposés selon l’échelle', () => {
      // 80 : « Critique » en exposition, « Solide » en maturité. C'est
      // exactement l'ambiguïté qui existait, désormais explicite.
      const { unmount } = render(<ScoreGauge score={80} scale="exposure" />)
      expect(screen.getByText('Critique')).toBeInTheDocument()
      unmount()

      render(<ScoreGauge score={80} scale="maturity" />)
      expect(screen.getByText('Solide')).toBeInTheDocument()
    })
  })

  it('n’utilise jamais la couleur d’action pour exprimer une gravité', () => {
    // Règle non négociable : la couleur porte le risque, `accent` porte
    // l'action. Le niveau « préoccupant » empruntait `accent` faute d'un
    // quatrième palier — la teinte des boutons servait donc de gravité.
    const { container } = render(<ScoreGauge score={60} level="preoccupant" levelLabel="Préoccupant" />)

    const arc = container.querySelectorAll('circle')[1]
    expect(arc.getAttribute('stroke')).toBe('var(--color-risk-concern)')
  })
})
