import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { assertNoCriticalViolations, registerNewTenant, releaseE2ETenants, uniqueSuffix } from './helpers.js'

// Les emplacements de surveillance engagés par ce parcours retournent au
// pool partagé : sans cela, les exécutions suivantes se voient refuser
// l'inscription, et la garde a raison de le faire.
test.afterAll(() => {
  releaseE2ETenants()
})

// Flow (a): inscription -> diagnostic complet -> plan d'action.
// Every measure is answered "Non" (non-conforme) rather than "Oui", so the
// diagnostic produces score gaps and apps.actions.services.generate_action_plan
// (called on completion — apps/assessments/views.py) actually populates a
// non-empty kanban board, exercising the flow end to end rather than
// bottoming out in the empty state.
//
// The diagnostic is a one-domain-at-a-time wizard (10 ANSSI domains):
// answers are role="radio" segmented controls, and "Suivant" only appears
// until the last domain, where it becomes "Terminer l’évaluation" — the
// loop below answers the visible domain, then advances until that button
// is the one actually present in the DOM (not just visible-but-disabled).
test('inscription, diagnostic complet et plan d’action généré', async ({ page }) => {
  // 42 mesures ANSSI x 1 PUT+GET round-trip chacune contre le vrai backend
  // docker-compose, réparties sur 10 domaines, dépasse le timeout par
  // défaut de 60s.
  test.setTimeout(150_000)
  const suffix = uniqueSuffix()

  await registerNewTenant(page, {
    companyName: `E2E Diagnostic ${suffix}`,
    email: `e2e-diag-${suffix}@example.com`,
  })
  await expect(page).toHaveURL(/\/tableau-de-bord$/)

  await page.getByRole('link', { name: 'Diagnostic' }).click()
  await page.waitForURL(/\/diagnostic$/)
  await expect(page.getByRole('heading', { name: 'Diagnostic de maturité' })).toBeVisible()

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)

  const finishButton = page.getByRole('button', { name: 'Terminer l’évaluation' })
  const nextButton = page.getByRole('button', { name: 'Suivant' })
  let reachedLastDomain = false

  for (let domainIndex = 0; domainIndex < 20; domainIndex++) {
    const radios = page.getByRole('radio', { name: 'Non', exact: true })
    const count = await radios.count()
    expect(count).toBeGreaterThan(0)

    for (let i = 0; i < count; i++) {
      const responsePromise = page.waitForResponse(
        (response) => response.url().includes('/answers/') && response.request().method() === 'PUT'
      )
      await radios.nth(i).click()
      await responsePromise
    }

    // The wizard renders either "Suivant" or "Terminer l’évaluation", never
    // both — but which one only settles in the DOM once React re-renders
    // after the last PUT/GET pair above resolves, which is not guaranteed
    // to have happened yet just because the network promise did. Waiting
    // on the combined locator (rather than a bare .count() snapshot) lets
    // Playwright's auto-retry absorb that render race.
    await finishButton.or(nextButton).waitFor()

    // "Terminer l’évaluation" only exists in the DOM on the last domain.
    if ((await finishButton.count()) > 0) {
      reachedLastDomain = true
      await expect(finishButton).toBeEnabled()
      await finishButton.click()
      break
    }
    await nextButton.click()
  }
  expect(reachedLastDomain).toBe(true)

  // Generous timeout: this click's request also runs
  // apps.actions.services.generate_action_plan server-side (42 gap
  // measures -> 42 ActionItem rows) before the response comes back.
  await expect(page.getByRole('heading', { name: 'Diagnostic terminé' })).toBeVisible({
    timeout: 15_000,
  })
  await page.getByRole('link', { name: 'Voir mes résultats' }).click()

  await page.waitForURL(/\/resultats\/\d+$/)
  await expect(page.getByRole('heading', { name: 'Résultats' })).toBeVisible()
  await expect(page.getByText('Score global de maturité')).toBeVisible()

  await page.getByRole('link', { name: 'Plan d’action' }).click()
  await page.waitForURL(/\/plan-action$/)

  // Every measure was answered "Non" (a full-scope gap), so at least one
  // action card must render — this is what actually proves
  // generate_action_plan ran, not just that the page loaded onto its empty
  // state ("Aucune action en attente..."). Generous timeout: the page does
  // 4+ sequential/parallel round-trips (paginated actionsApi.listAll,
  // tenantsApi.listMembers, actionsApi.projectedScore) for 42 items.
  await expect(page.getByText(/^Priorité \d+(\.\d+)?$/).first()).toBeVisible({ timeout: 15_000 })

  await new AxeBuilder({ page }).exclude('svg').analyze().then(assertNoCriticalViolations)
})
