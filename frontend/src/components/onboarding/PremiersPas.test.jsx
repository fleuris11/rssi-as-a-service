import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import PremiersPas from './PremiersPas'

// Lot C, point 21. Ce que ces tests tiennent : l'ordre des trois étapes, un
// « fait » qui vient des données et pas d'un clic, une troisième étape
// fermée tant qu'il n'y a pas de résultat à comprendre, et le message sur le
// premier scan au moment où il sert.

vi.mock('../../context/EntitlementsContext', () => ({
  useEntitlements: () => ({
    hasFeature: () => true,
    featureInfo: () => null,
    requiredPlanFor: () => '',
    isOperational: true,
    loading: false,
  }),
}))

function rendre(props = {}) {
  return render(
    <MemoryRouter>
      <PremiersPas aUnActif={false} aUnDiagnostic={false} resultatCompris={false} {...props} />
    </MemoryRouter>
  )
}

function etapes() {
  return within(screen.getByRole('list')).getAllByRole('listitem')
}

describe('PremiersPas', () => {
  it('propose les trois étapes dans l’ordre de la consigne', () => {
    rendre()

    const titres = etapes().map((etape) => within(etape).getByText(/^(Déclarez|Faites|Comprenez)/).textContent)
    expect(titres).toEqual([
      'Déclarez un actif',
      'Faites votre diagnostic',
      'Comprenez votre premier résultat',
    ])
  })

  it('explique, dès l’étape de l’actif, qu’un premier scan remonte l’historique', () => {
    rendre()

    expect(
      within(etapes()[0]).getByText(/Le premier scan remonte tout l’historique connu/)
    ).toBeInTheDocument()
    expect(within(etapes()[0]).getByText(/C’est normal, ce n’est pas un incident du jour/)).toBeInTheDocument()
  })

  it('écrit l’état de chaque étape, lu dans les données', () => {
    rendre({ aUnActif: true, aUnDiagnostic: false })

    expect(within(etapes()[0]).getByText('Fait')).toBeInTheDocument()
    expect(within(etapes()[1]).getByText('À faire')).toBeInTheDocument()
    expect(screen.getByText(/1 étape sur 3/)).toBeInTheDocument()
  })

  it('ferme la troisième étape tant qu’aucun diagnostic n’est terminé', () => {
    rendre({ aUnActif: true, aUnDiagnostic: false })

    const troisieme = etapes()[2]
    expect(within(troisieme).getByText('Après le diagnostic')).toBeInTheDocument()
    expect(within(troisieme).queryByRole('link')).not.toBeInTheDocument()
  })

  it('ouvre la troisième étape une fois le diagnostic terminé', () => {
    rendre({ aUnActif: true, aUnDiagnostic: true })

    expect(within(etapes()[2]).getByRole('link', { name: /Voir mon résultat/ })).toHaveAttribute(
      'href',
      '/resultats'
    )
  })

  it('se masque à la demande', async () => {
    const onMasquer = vi.fn()
    rendre({ onMasquer })

    await userEvent.click(screen.getByRole('button', { name: 'Masquer l’accueil' }))

    expect(onMasquer).toHaveBeenCalled()
  })
})
