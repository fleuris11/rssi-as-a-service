import { expect, test } from '@playwright/test'
import { auditAccessibility, getCurrentTenantSlug, registerNewTenant, releaseE2ETenants, simulateAssetDown, uniqueSuffix, waitForContentLoaded } from './helpers.js'

// Les emplacements de surveillance engagés par ce parcours retournent au
// pool partagé : sans cela, les exécutions suivantes se voient refuser
// l'inscription, et la garde a raison de le faire.
test.afterAll(() => {
  releaseE2ETenants()
})

// Flow (b): déclaration d'actif -> check simulé -> alerte visible.
// The "check simulé" step goes through the real alert engine
// (apps.monitoring.services.simulate_check_result / evaluate_alerts) via the
// `simulate_check_failure` management command run inside the docker-compose
// `web` container — CLAUDE.md forbids active/intrusive checks even in tests,
// so this deliberately does NOT hit a real URL, it injects 3 consecutive
// CRITICAL http_uptime CheckResults the same way a real outage would.
test('déclaration d’un actif puis alerte visible après un check en échec', async ({ page }) => {
  const suffix = uniqueSuffix()
  const assetUrl = `https://e2e-down-${suffix}.example.com`

  await registerNewTenant(page, {
    companyName: `E2E Surveillance ${suffix}`,
    email: `e2e-surv-${suffix}@example.com`,
  })

  await page.goto('/surveillance')

  await waitForContentLoaded(page)
  await expect(page.getByRole('heading', { name: 'Surveillance' })).toBeVisible()
  await expect(page.getByText('Aucune alerte ouverte.')).toBeVisible()

  await auditAccessibility(page)

  // Two "Déclarer un actif" buttons exist while the asset list is empty
  // (the page header action and the EmptyState's own CTA) — .first() picks
  // either, both open the same modal.
  await page.getByRole('button', { name: 'Déclarer un actif' }).first().click()
  await expect(page.getByRole('dialog', { name: 'Déclarer un actif' })).toBeVisible()

  await page.getByLabel('Type').selectOption('website')
  await page.getByLabel('URL (https://...)').fill(assetUrl)
  await page
    .getByText('Je certifie être propriétaire de cet actif', { exact: false })
    .click()
  await page.getByRole('button', { name: 'Ajouter' }).click()

  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.getByText(assetUrl)).toBeVisible()

  const tenantSlug = await getCurrentTenantSlug(page)
  simulateAssetDown({ tenantSlug, assetValue: assetUrl })

  await page.reload()

  await expect(page.getByText('1 alerte ouverte.')).toBeVisible()
  await expect(page.getByText('Site indisponible')).toBeVisible()

  await auditAccessibility(page)
})
