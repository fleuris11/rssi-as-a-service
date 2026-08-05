import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { assertNoCriticalViolations, registerNewTenant, uniqueSuffix } from './helpers.js'

// Flow (a): inscription -> diagnostic complet -> plan d'action.
// Every measure is answered "Non" (non-conforme) rather than "Oui", so the
// diagnostic produces score gaps and apps.actions.services.generate_action_plan
// (called on completion — apps/assessments/views.py) actually populates a
// non-empty kanban board, exercising the flow end to end rather than
// bottoming out in the empty state.
test('inscription, diagnostic complet et plan d’action généré', async ({ page }) => {
  // 42 mesures ANSSI (docs/adr/006...) x 1 PUT+GET round-trip chacune contre
  // le vrai backend docker-compose dépasse le timeout par défaut de 60s.
  test.setTimeout(120_000)
  const suffix = uniqueSuffix()

  await registerNewTenant(page, {
    companyName: `E2E Diagnostic ${suffix}`,
    email: `e2e-diag-${suffix}@example.com`,
  })
  await expect(page).toHaveURL(/\/diagnostic$/)
  await expect(page.getByRole('heading', { name: 'Diagnostic de maturité' })).toBeVisible()

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)

  const nonButtons = page.getByRole('button', { name: 'Non', exact: true })
  const measureCount = await nonButtons.count()
  expect(measureCount).toBeGreaterThan(0)

  for (let i = 0; i < measureCount; i++) {
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes('/answers/') && response.request().method() === 'PUT'
    )
    await nonButtons.nth(i).click()
    await responsePromise
  }

  const finishButton = page.getByRole('button', { name: "Terminer l'évaluation" })
  await expect(finishButton).toBeEnabled()
  await finishButton.click()

  await page.waitForURL(/\/resultats\/\d+$/)
  await expect(page.getByRole('heading', { name: 'Résultats' })).toBeVisible()
  await expect(page.getByText('Score global de maturité')).toBeVisible()

  await page.getByRole('link', { name: 'Plan d’action' }).click()
  await page.waitForURL(/\/plan-action$/)

  // Every measure was answered "Non" (a full-scope gap), so at least one
  // action card must render — this is what actually proves
  // generate_action_plan ran, not just that the page loaded onto its empty
  // state ("Aucune action en attente...").
  await expect(page.getByText(/^Priorité \d+$/).first()).toBeVisible()

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)
})
