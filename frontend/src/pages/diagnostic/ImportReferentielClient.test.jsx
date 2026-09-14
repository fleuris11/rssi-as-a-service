import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ImportReferentielClient from './ImportReferentielClient'

vi.mock('../../api/endpoints', () => ({
  assessmentsApi: { importReferential: vi.fn(), referentialTemplate: vi.fn() },
}))
const showToast = vi.fn()
vi.mock('../../components/ui/Toast', () => ({ useToast: () => ({ showToast }) }))

const { assessmentsApi } = await import('../../api/endpoints')

async function preparer() {
  render(<ImportReferentielClient onImporte={onImporte} />)
  await userEvent.click(screen.getByRole('button', { name: 'Importer votre propre référentiel' }))
  const fichier = new File(['{"domains": []}'], 'charte.json', { type: 'application/json' })
  await userEvent.upload(screen.getByLabelText('Fichier du référentiel'), fichier)
  await screen.findByText('charte.json')
  await userEvent.type(screen.getByLabelText('Nom du référentiel'), 'Notre charte')
}

const onImporte = vi.fn()

describe('ImportReferentielClient', () => {
  beforeEach(() => vi.clearAllMocks())

  it('analyse puis confirme, et rend la main à l’écran', async () => {
    const apercu = { name: 'Notre charte', domain_count: 1, measure_count: 5, will_update: false }
    assessmentsApi.importReferential
      .mockResolvedValueOnce({ data: { errors: [], preview: apercu, imported: false } })
      .mockResolvedValueOnce({
        data: { errors: [], preview: apercu, imported: true, slug: 'crrh-notre-charte' },
      })
    await preparer()

    await userEvent.click(screen.getByRole('button', { name: 'Analyser le fichier' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Confirmer l’import' }))

    await waitFor(() => expect(onImporte).toHaveBeenCalledWith('crrh-notre-charte'))
    expect(assessmentsApi.importReferential.mock.calls[1][0]).toMatchObject({
      name: 'Notre charte',
      confirm: true,
    })
  })

  it('explique qu’il faut être administrateur, plutôt qu’une erreur vague', async () => {
    assessmentsApi.importReferential.mockRejectedValue({ response: { status: 403, data: {} } })
    await preparer()

    await userEvent.click(screen.getByRole('button', { name: 'Analyser le fichier' }))

    expect(
      await screen.findByText(/Seul un administrateur de votre entreprise/)
    ).toBeInTheDocument()
  })
})
