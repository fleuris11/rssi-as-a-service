import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ConfirmDialog from './ConfirmDialog'

// Ce composant garde les seules actions irréversibles de la console. Ce qui
// est verrouillé ici : on annonce CE QUI VA SE PASSER (pas « êtes-vous
// sûr ? »), et une suppression définitive exige de retaper le nom.

describe('ConfirmDialog', () => {
  it('énonce les conséquences plutôt qu’une question vague', () => {
    render(
      <ConfirmDialog
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Archiver cette entreprise ?"
        summary="Atelier Roux sortira des listes actives."
        consequences={[
          'Son abonnement est résilié : ses emplacements retournent au pool partagé.',
          'Aucune donnée n’est détruite.',
        ]}
      />
    )

    expect(screen.getByText('Ce qui va se passer')).toBeInTheDocument()
    expect(screen.getByText(/retournent au pool partagé/)).toBeInTheDocument()
    expect(screen.getByText(/Aucune donnée n’est détruite/)).toBeInTheDocument()
  })

  it('confirme directement quand aucune saisie n’est exigée', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(<ConfirmDialog open onClose={vi.fn()} onConfirm={onConfirm} title="Archiver ?" />)

    await user.click(screen.getByRole('button', { name: 'Confirmer' }))

    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('bloque la suppression tant que le nom n’est pas retapé exactement', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(
      <ConfirmDialog
        open
        onClose={vi.fn()}
        onConfirm={onConfirm}
        title="Suppression définitive"
        confirmText="Atelier Roux"
        confirmLabel="Supprimer définitivement"
        danger
      />
    )

    const button = screen.getByRole('button', { name: 'Supprimer définitivement' })
    expect(button).toBeDisabled()

    await user.type(screen.getByLabelText(/Retapez/), 'Atelier Rou')
    expect(button).toBeDisabled()

    await user.type(screen.getByLabelText(/Retapez/), 'x')
    expect(button).toBeEnabled()

    await user.click(button)
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('repart d’un champ vide à chaque réouverture', async () => {
    const { rerender } = render(
      <ConfirmDialog open onClose={vi.fn()} onConfirm={vi.fn()} title="X" confirmText="Cible" />
    )
    const user = userEvent.setup()
    await user.type(screen.getByLabelText(/Retapez/), 'Cible')

    rerender(
      <ConfirmDialog
        open={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="X"
        confirmText="Cible"
      />
    )
    rerender(
      <ConfirmDialog open onClose={vi.fn()} onConfirm={vi.fn()} title="X" confirmText="Cible" />
    )

    // Sinon, rouvrir la boîte sur une AUTRE entreprise laisserait le bouton
    // déjà déverrouillé par la saisie précédente.
    expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
  })
})
