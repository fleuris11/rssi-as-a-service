import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ImportReferentiel from './ImportReferentiel'

// L'import en console : ce qui compte, c'est l'ORDRE des gestes. On analyse,
// on voit toutes les erreurs ou l'aperçu, et seulement ensuite on confirme.

vi.mock('../../../../api/endpoints', () => ({
  platformApi: { importReferential: vi.fn(), referentialTemplate: vi.fn() },
}))
const showToast = vi.fn()
vi.mock('../../../../components/ui/Toast', () => ({ useToast: () => ({ showToast }) }))

const { platformApi } = await import('../../../../api/endpoints')

const APERCU = {
  slug: 'iso-test',
  name: 'ISO de test',
  version: '2022',
  domain_count: 1,
  measure_count: 3,
  will_update: false,
  existing_measure_count: 0,
  domains: [{ code: 'org', name: 'Organisation', measure_count: 3, measures: [] }],
}

async function deposer(contenu = 'domaine_code;mesure_code\nd;1\n') {
  const fichier = new File([contenu], 'referentiel.csv', { type: 'text/csv' })
  await userEvent.upload(screen.getByLabelText('Fichier du référentiel'), fichier)
  await screen.findByText('referentiel.csv')
}

describe('ImportReferentiel', () => {
  beforeEach(() => vi.clearAllMocks())

  it('montre toutes les erreurs avec leur ligne, et n’offre pas de confirmer', async () => {
    platformApi.importReferential.mockRejectedValue({
      response: {
        data: {
          errors: [
            { ligne: 3, message: 'Colonne(s) obligatoire(s) vide(s) : mesure_code.' },
            { ligne: 4, message: 'Énoncé en langage clair manquant.' },
          ],
        },
      },
    })
    render(<ImportReferentiel />)
    await deposer()

    await userEvent.click(screen.getByRole('button', { name: 'Analyser le fichier' }))

    expect(await screen.findByText(/2 problèmes à corriger/)).toBeInTheDocument()
    expect(screen.getByText('Ligne 3 :')).toBeInTheDocument()
    expect(screen.getByText('Ligne 4 :')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Confirmer l’import' })).not.toBeInTheDocument()
  })

  it('analyse sans confirmer, puis confirme sur l’aperçu', async () => {
    const onImporte = vi.fn()
    platformApi.importReferential
      .mockResolvedValueOnce({ data: { errors: [], preview: APERCU, imported: false } })
      .mockResolvedValueOnce({ data: { errors: [], preview: APERCU, imported: true } })
    render(<ImportReferentiel onImporte={onImporte} />)
    await deposer()

    await userEvent.click(screen.getByRole('button', { name: 'Analyser le fichier' }))
    expect(await screen.findByText(/1 domaine\(s\), 3 mesure\(s\)/)).toBeInTheDocument()
    // Le premier appel n'engage rien.
    expect(platformApi.importReferential.mock.calls[0][0].confirm).toBeUndefined()

    await userEvent.click(screen.getByRole('button', { name: 'Confirmer l’import' }))

    await waitFor(() =>
      expect(platformApi.importReferential.mock.calls[1][0]).toMatchObject({ confirm: true })
    )
    expect(onImporte).toHaveBeenCalled()
  })

  it('prévient quand l’import remplacera un référentiel existant', async () => {
    platformApi.importReferential.mockResolvedValue({
      data: {
        errors: [],
        preview: { ...APERCU, will_update: true, existing_measure_count: 42 },
        imported: false,
      },
    })
    render(<ImportReferentiel />)
    await deposer()

    await userEvent.click(screen.getByRole('button', { name: 'Analyser le fichier' }))

    expect(await screen.findByText(/existe déjà \(42 mesures\)/)).toBeInTheDocument()
  })

  it('n’analyse rien tant qu’aucun fichier n’est choisi', () => {
    render(<ImportReferentiel />)

    expect(screen.getByRole('button', { name: 'Analyser le fichier' })).toBeDisabled()
  })
})
