import { expect, test } from '@playwright/test'
import { auditAccessibility, registerNewTenant, releaseE2ETenants, uniqueSuffix, waitForContentLoaded } from './helpers.js'

// Les emplacements de surveillance engagés par ce parcours retournent au
// pool partagé : sans cela, les exécutions suivantes se voient refuser
// l'inscription, et la garde a raison de le faire.
test.afterAll(() => {
  releaseE2ETenants()
})

// RGAA baseline (mission Phase 5, point 8): the 3 critical-flow specs already
// scan the pages they pass through, but several principal pages aren't on
// any of those 3 paths (Résultats before a diagnostic exists, Assistant,
// Préférences, Sécurité, and the two public auth pages). This sweep covers
// what they don't, so every page reachable from the main nav gets at least
// one axe-core pass.
test('pages publiques (connexion, inscription) sans violation critique', async ({ page }) => {
  await page.goto('/connexion')
  await waitForContentLoaded(page)
  await expect(page.getByRole('button', { name: 'Se connecter' })).toBeVisible()
  await auditAccessibility(page)

  await page.goto('/inscription')

  await waitForContentLoaded(page)
  await expect(page.getByRole('button', { name: 'Créer mon compte' })).toBeVisible()
  await auditAccessibility(page)
})

test('pages principales authentifiées sans violation critique', async ({ page }) => {
  const suffix = uniqueSuffix()
  await registerNewTenant(page, {
    companyName: `E2E A11y ${suffix}`,
    email: `e2e-a11y-${suffix}@example.com`,
  })

  const pages = [
    // A fresh tenant has no completed assessment yet, so this is the
    // 3-step onboarding view, not the populated dashboard — still worth
    // scanning as its own real state.
    { path: '/tableau-de-bord', text: 'Bienvenue sur RSSI as a Service' },
    // No heading here: a fresh tenant has no completed assessment yet, so
    // this renders ResultsPage's empty state ("Aucune évaluation
    // terminée...") rather than the h1 — still a real page state worth
    // scanning.
    { path: '/resultats', text: 'Aucune évaluation terminée' },
    { path: '/compromissions', heading: 'Compromissions' },
    { path: '/assistant', heading: 'Assistant' },
    { path: '/preferences', heading: 'Préférences de notification' },
    { path: '/securite', heading: 'Sécurité du compte' },
  ]

  for (const { path, heading, text } of pages) {
    await page.goto(path)
    await waitForContentLoaded(page)
        if (heading) {
      await expect(page.getByRole('heading', { name: heading })).toBeVisible()
    }
    if (text) {
      await expect(page.getByText(text, { exact: false })).toBeVisible()
    }
    await auditAccessibility(page)
  }
})
