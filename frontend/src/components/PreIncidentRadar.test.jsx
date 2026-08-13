import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import PreIncidentRadar from './PreIncidentRadar'

// La carte porte deux choses qui se cassent silencieusement : les actions de
// traitement (déplacées ici en Phase 8C, sans quoi un signal retiré de la
// liste deviendrait intraitable) et l'état vide, qui est un message
// commercial autant qu'un état d'interface.

const TYPOSQUAT_SIGNAL = {
  signal_type: 'typosquat',
  label: 'Nom de domaine imitant le vôtre',
  plain_language: 'Quelqu’un a déposé une adresse internet très proche de la vôtre.',
  urgency: 'high',
  count: 2,
  items: [
    { id: 1, asset_value: 'a.fr', detail: 'exemp1e.fr', detected_at: null, breach_date: null },
    { id: 2, asset_value: 'a.fr', detail: 'exemp1e.co', detected_at: null, breach_date: null },
  ],
}

describe('PreIncidentRadar', () => {
  it('n’affiche rien tant que les données ne sont pas chargées', () => {
    const { container } = render(<PreIncidentRadar summary={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  describe('état vide', () => {
    it('affiche un message rassurant plutôt qu’un vide', () => {
      render(<PreIncidentRadar summary={{ signals: [], total: 0 }} />)

      // Cet état est montré en démonstration : « rien à signaler » doit se
      // lire comme une bonne nouvelle, pas comme un écran cassé.
      expect(screen.getByText(/votre exposition publique est calme/i)).toBeInTheDocument()
    })

    it('adapte le message en mode historique', () => {
      render(
        <PreIncidentRadar summary={{ signals: [], total: 0 }} showingHistory onToggleHistory={vi.fn()} />
      )
      expect(screen.getByText(/Aucun signal traité/)).toBeInTheDocument()
    })
  })

  describe('affichage des signaux', () => {
    it('affiche le libellé, la vulgarisation et le niveau d’urgence', () => {
      render(<PreIncidentRadar summary={{ signals: [TYPOSQUAT_SIGNAL], total: 2 }} />)

      expect(screen.getByText('Nom de domaine imitant le vôtre')).toBeInTheDocument()
      expect(screen.getByText(/Quelqu’un a déposé une adresse internet/)).toBeInTheDocument()
      expect(screen.getByText('À traiter')).toBeInTheDocument()
      expect(screen.getByText('exemp1e.fr')).toBeInTheDocument()
      expect(screen.getByText('exemp1e.co')).toBeInTheDocument()
    })

    it('signale le nombre de détections quand il y en a plusieurs', () => {
      render(<PreIncidentRadar summary={{ signals: [TYPOSQUAT_SIGNAL], total: 2 }} />)
      expect(screen.getByText('2 détections')).toBeInTheDocument()
    })
  })

  describe('actions de traitement', () => {
    it('permet de marquer un signal traité depuis la carte', async () => {
      const user = userEvent.setup()
      const onUpdateStatus = vi.fn()
      render(
        <PreIncidentRadar
          summary={{ signals: [TYPOSQUAT_SIGNAL], total: 2 }}
          onUpdateStatus={onUpdateStatus}
        />
      )

      await user.click(screen.getAllByRole('button', { name: 'Marquer traité' })[0])

      expect(onUpdateStatus).toHaveBeenCalledWith(1, 'treated')
    })

    it('permet d’ignorer un signal depuis la carte', async () => {
      const user = userEvent.setup()
      const onUpdateStatus = vi.fn()
      render(
        <PreIncidentRadar
          summary={{ signals: [TYPOSQUAT_SIGNAL], total: 2 }}
          onUpdateStatus={onUpdateStatus}
        />
      )

      await user.click(screen.getAllByRole('button', { name: 'Ignorer' })[1])

      expect(onUpdateStatus).toHaveBeenCalledWith(2, 'ignored')
    })

    it('désactive les actions du signal en cours de traitement', () => {
      render(
        <PreIncidentRadar
          summary={{ signals: [TYPOSQUAT_SIGNAL], total: 2 }}
          onUpdateStatus={vi.fn()}
          busyId={1}
        />
      )

      expect(screen.getAllByRole('button', { name: 'Marquer traité' })[0]).toBeDisabled()
      expect(screen.getAllByRole('button', { name: 'Marquer traité' })[1]).toBeEnabled()
    })

    it('retire les actions en mode historique (signaux déjà traités)', () => {
      render(
        <PreIncidentRadar
          summary={{ signals: [TYPOSQUAT_SIGNAL], total: 2 }}
          onUpdateStatus={vi.fn()}
          showingHistory
          onToggleHistory={vi.fn()}
        />
      )

      expect(screen.queryByRole('button', { name: 'Marquer traité' })).not.toBeInTheDocument()
    })
  })

  describe('bascule vers l’historique', () => {
    it('propose de voir les signaux traités', async () => {
      const user = userEvent.setup()
      const onToggleHistory = vi.fn()
      render(
        <PreIncidentRadar
          summary={{ signals: [TYPOSQUAT_SIGNAL], total: 2 }}
          onToggleHistory={onToggleHistory}
        />
      )

      await user.click(screen.getByRole('button', { name: /Voir les signaux traités/ }))

      expect(onToggleHistory).toHaveBeenCalled()
    })
  })
})
