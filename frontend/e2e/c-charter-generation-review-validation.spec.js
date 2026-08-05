import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { assertNoCriticalViolations, registerNewTenant, uniqueSuffix } from './helpers.js'

// Flow (c): génération de charte (API mockée) -> relecture -> validation.
// CLAUDE.md forbids AI calls in the request/response cycle and this suite
// must stay free (and deterministic) — so every /api/v1/ai/** call is
// intercepted here rather than exercising the real Celery job + Anthropic
// API pipeline (that pipeline has its own backend-side tests, see
// apps/ai_assistant/tests/). This spec only proves the frontend's
// generate -> poll -> review -> validate flow wires together correctly.
const DOCUMENT_ID = 4242
const JOB_ID = 9999
const GENERATED_MARKDOWN = '# Charte informatique\n\nBienvenue chez Entreprise E2E.\n\n## Mots de passe\n\n12 caractères minimum.'

test('génération de charte mockée, relecture puis validation', async ({ page }) => {
  const suffix = uniqueSuffix()
  let documentStatus = 'generating'

  await page.route('**/api/v1/ai/settings/', (route) =>
    route.fulfill({
      json: {
        ai_enabled: true,
        quota: { tokens_used: 1000, monthly_token_limit: 200000, remaining_tokens: 199000 },
      },
    })
  )

  await page.route('**/api/v1/ai/documents/', (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    documentStatus = 'generating'
    return route.fulfill({
      status: 202,
      json: {
        document: {
          id: DOCUMENT_ID,
          type: 'it_charter',
          version: 1,
          status: 'generating',
          content_markdown: '',
        },
        job: { id: JOB_ID, status: 'pending' },
      },
    })
  })

  let jobPollCount = 0
  await page.route(`**/api/v1/ai/jobs/${JOB_ID}/`, (route) => {
    // First poll still pending (exercises the "Génération en cours" state),
    // every poll after that reports done — keeps the test fast without
    // skipping the in-progress UI entirely.
    jobPollCount += 1
    const status = jobPollCount === 1 ? 'pending' : 'done'
    if (status === 'done') documentStatus = 'draft'
    return route.fulfill({ json: { id: JOB_ID, status } })
  })

  await page.route(`**/api/v1/ai/documents/${DOCUMENT_ID}/`, (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    return route.fulfill({
      json: {
        id: DOCUMENT_ID,
        type: 'it_charter',
        version: 1,
        status: documentStatus,
        content_markdown: documentStatus === 'generating' ? '' : GENERATED_MARKDOWN,
      },
    })
  })

  await page.route(`**/api/v1/ai/documents/${DOCUMENT_ID}/export/pdf/`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      headers: { 'Content-Disposition': 'attachment; filename="it_charter-v1.pdf"' },
      body: Buffer.from('%PDF-1.4 fake e2e content'),
    })
  )

  await page.route(`**/api/v1/ai/documents/${DOCUMENT_ID}/validate/`, (route) => {
    documentStatus = 'validated'
    return route.fulfill({
      json: {
        id: DOCUMENT_ID,
        type: 'it_charter',
        version: 1,
        status: 'validated',
        content_markdown: GENERATED_MARKDOWN,
      },
    })
  })

  await registerNewTenant(page, {
    companyName: `E2E Charte ${suffix}`,
    email: `e2e-charte-${suffix}@example.com`,
  })

  await page.goto('/documents')
  await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible()

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)

  await page.getByRole('button', { name: 'Générer la charte informatique' }).click()

  // Génération : the polling in-progress state must show before settling.
  await expect(page.getByText('Génération en cours par l’IA')).toBeVisible()

  // Relecture : once the (mocked) job settles, the generated content loads
  // into the editable review textarea. "Brouillon" renders both in the
  // document list entry and the editor's status badge, hence .first().
  await expect(page.getByText('Brouillon').first()).toBeVisible()
  const textarea = page.getByRole('textbox')
  await expect(textarea).toHaveValue(GENERATED_MARKDOWN)

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)

  // Export PDF (US-4.1, ADR-012) — available before validation too, same as
  // the markdown export.
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Exporter (.pdf)' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('it_charter-v1.pdf')

  // Validation.
  await page.getByRole('button', { name: 'Valider' }).click()
  await expect(page.getByText('Validé', { exact: true }).first()).toBeVisible()
  await expect(textarea).toHaveAttribute('readonly')

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)
})
