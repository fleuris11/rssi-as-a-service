import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import {
  API_BASE_URL,
  registerNewTenant,
  releaseE2ETenants,
  uniqueSuffix,
  waitForContentLoaded,
} from './helpers.js'

/**
 * Phase 12 — les gardes de fonctionnalité, vues d'un vrai navigateur.
 *
 * Ce qui se joue ici ne se teste pas en unitaire : que la règle vendue est
 * appliquée **de bout en bout**, et que le client hors offre voit un argument
 * de vente plutôt qu'un écran cassé.
 *
 * Trois choses sont vérifiées ensemble, et c'est leur conjonction qui compte :
 *
 * 1. l'élément reste **visible et désactivé**, avec le nom de l'offre — jamais
 *    masqué (règle posée en phase 10 : on ne cache pas, on donne envie) ;
 * 2. l'API refuse le **même** appel en 402, indépendamment de ce que montre
 *    l'interface — sans quoi la garde ne serait qu'un grisé contournable avec
 *    la console du navigateur ;
 * 3. la même entreprise, passée sur l'offre qui comprend la fonctionnalité,
 *    y accède réellement. Un test qui ne vérifierait que le refus passerait au
 *    vert sur une garde bloquant tout le monde.
 */

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

function djangoShell(script) {
  return execFileSync(
    'docker',
    ['compose', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '--no-imports', '-c', script],
    { cwd: REPO_ROOT, encoding: 'utf-8' }
  ).trim()
}

/** Place l'entreprise sur une offre du catalogue, comme le ferait la console. */
function setPlan(tenantSlug, planCode) {
  return djangoShell(
    [
      'from apps.billing.models import Plan, Subscription',
      `s = Subscription.objects.get(tenant__slug="${tenantSlug}")`,
      `s.plan = Plan.objects.get(code="${planCode}")`,
      's.override_features = None',
      's.save(update_fields=["plan", "override_features"])',
      'print(s.plan.code, sorted(s.effective_features))',
    ].join('\n')
  )
}

async function tenantSlug(page) {
  return page.evaluate(async (apiBaseUrl) => {
    const access = localStorage.getItem('rssi.access')
    const response = await fetch(`${apiBaseUrl}/api/v1/auth/me/`, {
      headers: { Authorization: `Bearer ${access}` },
    })
    return (await response.json()).memberships[0].tenant_slug
  }, API_BASE_URL)
}

/** Rejoue l'appel gardé depuis le navigateur, avec le jeton déjà en place —
 * c'est-à-dire exactement ce que ferait un client qui contourne l'interface. */
async function callApi(page, method, endpoint) {
  return page.evaluate(
    async ([apiBaseUrl, verb, chemin]) => {
      const access = localStorage.getItem('rssi.access')
      const tenantId = localStorage.getItem('rssi.tenantId')
      const response = await fetch(`${apiBaseUrl}${chemin}`, {
        method: verb,
        headers: {
          Authorization: `Bearer ${access}`,
          'X-Tenant-Id': tenantId,
          'Content-Type': 'application/json',
        },
        body: verb === 'GET' ? undefined : '{}',
      })
      let corps = null
      try {
        corps = await response.json()
      } catch {
        corps = null
      }
      return { status: response.status, body: corps }
    },
    [API_BASE_URL, method, endpoint]
  )
}

test.describe('Gardes de fonctionnalité par offre', () => {
  test.afterAll(() => {
    releaseE2ETenants(['E2E Gardes '])
  })

  test('hors offre : désactivé et expliqué à l’écran, refusé par l’API', async ({ page }) => {
    const suffixe = uniqueSuffix()
    const nom = `E2E Gardes ${suffixe}`
    await registerNewTenant(page, { companyName: nom, email: `gardes-${suffixe}@example.com` })

    const slug = await tenantSlug(page)
    // « Veille » à 89 € : la surveillance, et rien de ce qui est vendu avec
    // « Pilotage » à 249 €.
    setPlan(slug, 'veille')

    await page.goto('/tableau-de-bord')
    await waitForContentLoaded(page)

    // 1. VISIBLE — la carte du diagnostic est toujours là. La masquer
    // laisserait croire que le produit ne sait pas faire de diagnostic.
    await expect(page.getByText('Faites votre diagnostic')).toBeVisible()

    // 2. DÉSACTIVÉE — dans un conteneur marqué pour les technologies
    // d'assistance, pas seulement grisé en CSS.
    const verrou = page.locator('[data-feature-locked="anssi_assessment"]')
    await expect(verrou).toBeVisible()
    await expect(verrou).toHaveAttribute('aria-disabled', 'true')

    // 3. L'OFFRE EST NOMMÉE — un refus qui ne dit que « non » ne vend rien.
    await expect(page.getByText(/Compris à partir de l’offre Pilotage/).first()).toBeVisible()

    // 4. La page du diagnostic explique, au lieu d'annoncer une panne.
    await page.goto('/diagnostic')
    await waitForContentLoaded(page)
    await expect(page.getByText('Diagnostic de maturité').first()).toBeVisible()
    await expect(page.getByText(/Diagnostic indisponible/)).toHaveCount(0)
    await expect(page.getByText(/restent consultables/)).toBeVisible()

    // 5. L'API refuse le même appel — la garde n'est pas qu'un grisé.
    const direct = await callApi(page, 'POST', '/api/v1/assessments/start/')
    expect(direct.status).toBe(402)
    expect(direct.body.required_plan).toBeTruthy()

    // 6. Les autres clés de la même offre, par appel direct également.
    for (const chemin of [
      '/api/v1/ai/conversations/',
      '/api/v1/ai/documents/',
      '/api/v1/ai/documents/999999/export/pdf/',
    ]) {
      const refus = await callApi(page, chemin.endsWith('pdf/') ? 'GET' : 'POST', chemin)
      expect(refus.status, `${chemin} devrait être refusé sur « Veille »`).toBe(402)
    }
  })

  test('dans l’offre : la même entreprise accède au diagnostic', async ({ page }) => {
    const suffixe = uniqueSuffix()
    const nom = `E2E Gardes ${suffixe}`
    await registerNewTenant(page, { companyName: nom, email: `gardes-ok-${suffixe}@example.com` })

    const slug = await tenantSlug(page)
    setPlan(slug, 'pilotage')

    await page.goto('/tableau-de-bord')
    await waitForContentLoaded(page)

    // Plus aucun verrou sur le diagnostic, et le bouton est cliquable.
    await expect(page.locator('[data-feature-locked="anssi_assessment"]')).toHaveCount(0)
    await expect(page.getByRole('link', { name: /Démarrer le diagnostic/ })).toBeVisible()

    // L'API accepte : ce n'est pas une garde qui bloque tout le monde.
    const direct = await callApi(page, 'POST', '/api/v1/assessments/start/')
    expect(direct.status).not.toBe(402)

    // Et le questionnaire s'ouvre réellement.
    await page.goto('/diagnostic')
    await waitForContentLoaded(page)
    await expect(page.getByText(/Domaine 1 \//)).toBeVisible()
  })
})
