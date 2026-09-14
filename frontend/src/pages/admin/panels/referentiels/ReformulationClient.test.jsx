import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ReformulationClient from './ReformulationClient'

vi.mock('../../../../api/endpoints', () => ({
  platformApi: {
    referentialOutline: vi.fn(),
    clientOverrides: vi.fn(),
    setClientOverride: vi.fn(),
    clearClientOverride: vi.fn(),
  },
}))
const showToast = vi.fn()
vi.mock('../../../../components/ui/Toast', () => ({ useToast: () => ({ showToast }) }))

const { platformApi } = await import('../../../../api/endpoints')

const PLAN = {
  slug: 'anssi',
  domains: [
    {
      code: 'd',
      name: 'D',
      measures: [
        { id: 11, code: '1', official_title: 'Former', plain_language: 'Énoncé d’origine ?' },
      ],
    },
  ],
  subsets: [],
}

async function ouvrir() {
  render(
    <ReformulationClient
      catalogue={[{ slug: 'anssi', name: 'ANSSI' }]}
      clients={[{ tenant_id: 'uuid-1', name: 'CRRH' }]}
    />
  )
  await userEvent.selectOptions(screen.getByLabelText('Client'), 'uuid-1')
  await userEvent.selectOptions(screen.getByLabelText('Référentiel à reformuler'), 'anssi')
}

describe('ReformulationClient', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    platformApi.referentialOutline.mockResolvedValue({ data: PLAN })
    platformApi.clientOverrides.mockResolvedValue({ data: { overrides: [] } })
  })

  it('garde l’énoncé d’origine sous les yeux', async () => {
    // Sans lui, on ne saurait plus ce qu'on a remplacé.
    await ouvrir()

    expect(await screen.findByText('Énoncé d’origine ?')).toBeInTheDocument()
  })

  it('enregistre la reformulation pour CE client, sur cette mesure', async () => {
    platformApi.setClientOverride.mockResolvedValue({
      data: { overrides: [{ measure_id: 11, plain_language: 'Dit autrement ?' }] },
    })
    await ouvrir()
    await screen.findByText('Énoncé d’origine ?')

    await userEvent.type(screen.getByLabelText('Reformulation de la mesure 1'), 'Dit autrement ?')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() =>
      expect(platformApi.setClientOverride).toHaveBeenCalledWith('uuid-1', {
        measure_id: 11,
        plain_language: 'Dit autrement ?',
      })
    )
    expect(await screen.findByText('Reformulée')).toBeInTheDocument()
  })

  it('permet de revenir à l’énoncé d’origine', async () => {
    platformApi.clientOverrides.mockResolvedValue({
      data: { overrides: [{ measure_id: 11, plain_language: 'Déjà reformulée ?' }] },
    })
    platformApi.clearClientOverride.mockResolvedValue({ data: { overrides: [] } })
    await ouvrir()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Revenir à l’énoncé d’origine' })
    )

    await waitFor(() => expect(platformApi.clearClientOverride).toHaveBeenCalledWith('uuid-1', 11))
  })

  it('n’enregistre pas une reformulation vide', async () => {
    await ouvrir()
    await screen.findByText('Énoncé d’origine ?')

    expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeDisabled()
  })
})
