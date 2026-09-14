import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EditionReferentiel from './EditionReferentiel'

vi.mock('../../../../api/endpoints', () => ({
  platformApi: {
    referentialOutline: vi.fn(),
    addReferentialDomain: vi.fn(),
    addReferentialMeasure: vi.fn(),
    composeSubset: vi.fn(),
  },
}))
const showToast = vi.fn()
vi.mock('../../../../components/ui/Toast', () => ({ useToast: () => ({ showToast }) }))

const { platformApi } = await import('../../../../api/endpoints')

const CATALOGUE = [{ slug: 'anssi', name: 'ANSSI' }]
const CLIENTS = [{ tenant_id: 'uuid-crrh', name: 'CRRH' }]
const PLAN = {
  slug: 'anssi',
  name: 'ANSSI',
  domains: [
    {
      code: 'sensibiliser',
      name: 'Sensibiliser',
      order: 1,
      measures: [
        { id: 1, code: '1', official_title: 'Former les équipes', plain_language: 'Formées ?' },
        { id: 2, code: '2', official_title: 'Sensibiliser', plain_language: 'Sensibilisés ?' },
      ],
    },
  ],
  subsets: [
    { slug: 'dix', name: 'Les 10 mesures essentielles', measure_codes: ['1'], owner_tenant_name: null },
    { slug: 'crrh', name: 'Questionnaire CRRH', measure_codes: ['1', '2'], owner_tenant_name: 'CRRH' },
  ],
}

describe('EditionReferentiel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    platformApi.referentialOutline.mockResolvedValue({ data: PLAN })
    platformApi.composeSubset.mockResolvedValue({ data: PLAN })
    platformApi.addReferentialMeasure.mockResolvedValue({ data: PLAN })
  })

  it('n’ajoute pas une mesure dont l’énoncé n’est pas rédigé', async () => {
    render(<EditionReferentiel catalogue={CATALOGUE} clients={CLIENTS} />)
    await screen.findByText('Structure')

    await userEvent.selectOptions(screen.getByLabelText('Domaine de la mesure'), 'sensibiliser')
    await userEvent.type(screen.getByLabelText('Code de la mesure'), '3')
    await userEvent.type(screen.getByLabelText('Intitulé officiel'), 'Un intitulé')

    // Sans énoncé en langage clair, la validation reste fermée.
    expect(screen.getByRole('button', { name: 'Ajouter la mesure' })).toBeDisabled()

    await userEvent.type(screen.getByLabelText('Énoncé en langage clair'), 'Une question ?')
    expect(screen.getByRole('button', { name: 'Ajouter la mesure' })).toBeEnabled()
  })

  it('compose un questionnaire POUR un client, avec les mesures cochées', async () => {
    render(<EditionReferentiel catalogue={CATALOGUE} clients={CLIENTS} />)
    await screen.findByText('Former les équipes')

    await userEvent.click(screen.getByRole('checkbox', { name: /Former les équipes/ }))
    await userEvent.type(screen.getByLabelText('Nom de la composition'), 'Pour CRRH')
    await userEvent.selectOptions(screen.getByLabelText('Pour'), 'uuid-crrh')
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer \(1\)/ }))

    await waitFor(() =>
      expect(platformApi.composeSubset).toHaveBeenCalledWith('anssi', {
        name: 'Pour CRRH',
        slug: 'pour-crrh',
        measure_codes: ['1'],
        tenant_id: 'uuid-crrh',
      })
    )
  })

  it('sans client désigné, publie un modèle de plateforme', async () => {
    render(<EditionReferentiel catalogue={CATALOGUE} clients={CLIENTS} />)
    await screen.findByText('Former les équipes')

    await userEvent.click(screen.getByRole('checkbox', { name: /Former les équipes/ }))
    await userEvent.type(screen.getByLabelText('Nom de la composition'), 'Modèle')
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer \(1\)/ }))

    await waitFor(() => expect(platformApi.composeSubset).toHaveBeenCalled())
    expect(platformApi.composeSubset.mock.calls[0][1]).not.toHaveProperty('tenant_id')
  })

  it('dit à qui appartient chaque composition', async () => {
    render(<EditionReferentiel catalogue={CATALOGUE} clients={CLIENTS} />)

    expect(await screen.findByText('Modèle de plateforme')).toBeInTheDocument()
    expect(screen.getByText('Propre à CRRH')).toBeInTheDocument()
  })
})
