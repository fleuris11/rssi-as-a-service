import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { registerNewTenant, uniqueSuffix } from './helpers.js'

/**
 * Phase 10 — administration plateforme et limites d'offre, en conditions
 * réelles (vrai navigateur, vrai backend, vraie base).
 *
 * Ce qui est vérifié ici ne peut pas l'être en test unitaire : que la ressource
 * rare de la plateforme (les emplacements de surveillance de la licence CTI,
 * partagés par TOUS les clients) est bien refusée à l'écran, avec un message
 * qui dit ce qu'il reste — et non constatée en dépassement après coup.
 */

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const ADMIN_EMAIL = 'admin-e2e@example.com'
const ADMIN_PASSWORD = 'AdminPlateforme2026!'

/** Exécute un script Django dans le conteneur web et renvoie sa sortie. */
function djangoShell(script) {
  return execFileSync(
    'docker',
    // --no-imports : sans lui, le shell Django préfixe sa sortie d'une
    // bannière (« N objects imported automatically ») qui parasite les
    // valeurs qu'on lit ici.
    ['compose', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '--no-imports', '-c', script],
    { cwd: REPO_ROOT, encoding: 'utf-8' }
  ).trim()
}

function ensurePlatformAdmin() {
  djangoShell(
    [
      'from apps.accounts.models import User',
      `u, _ = User.objects.get_or_create(email='${ADMIN_EMAIL}')`,
      'u.is_staff = True',
      'u.is_superuser = True',
      `u.set_password('${ADMIN_PASSWORD}')`,
      'u.save()',
    ].join('\n')
  )
}

/** Remplit le pool d'emplacements jusqu'au plafond, avec de VRAIS abonnements.
 *
 * On ne touche ni à la garde ni au réglage du plafond : on met la plateforme
 * dans l'état qu'elle aura réellement le jour où elle sera pleine. Les
 * entreprises créées portent un préfixe reconnaissable pour être retirées
 * ensuite. */
function fillMonitoredSlotPool(marker) {
  return djangoShell(
    [
      'from django.utils import timezone',
      'from django.utils.text import slugify',
      'from apps.billing import capacity',
      'from apps.billing.models import Plan, Subscription',
      'from apps.tenants.models import Tenant',
      'plan = Plan.objects.get(code="veille")',
      'created = 0',
      'while capacity.projected_monitored_slots(additional=0) < capacity.monitored_slot_capacity():',
      '    created += 1',
      `    name = "Bouchon ${marker} %d" % created`,
      '    t = Tenant.objects.create(name=name, slug=slugify(name))',
      '    Subscription.objects.create(tenant=t, plan=plan,',
      '        status=Subscription.Status.ACTIVE, started_at=timezone.now())',
      'print(capacity.projected_monitored_slots(additional=0), capacity.monitored_slot_capacity())',
    ].join('\n')
  )
}

function removeFillerTenants(marker) {
  djangoShell(
    [
      'from apps.tenants.models import Tenant',
      `Tenant.objects.filter(name__startswith="Bouchon ${marker}").delete()`,
    ].join('\n')
  )
}

/** Rend au pool les emplacements engagés par les entreprises de test.
 *
 * Sans ce nettoyage, chaque exécution laisse des essais ouverts qui remplissent
 * le pool partagé — et la garde de capacité finit, à juste titre, par refuser
 * les inscriptions des exécutions suivantes. */
function removeTestTenants() {
  djangoShell(
    [
      'from apps.tenants.models import Tenant',
      'for prefix in ["Bouchon ", "Prospect E2E", "Client Limite", "Client Suspendu"]:',
      '    Tenant.objects.filter(name__startswith=prefix).delete()',
    ].join('\n')
  )
}

async function loginAsPlatformAdmin(page) {
  await page.goto('/connexion')
  await page.getByLabel('Email').fill(ADMIN_EMAIL)
  await page.getByLabel('Mot de passe').fill(ADMIN_PASSWORD)
  await page.getByRole('button', { name: 'Se connecter' }).click()
  await page.waitForURL(/tableau-de-bord|admin/)
}

// Les emplacements de surveillance sont une ressource PARTAGÉE : un test qui
// en laisse d'engagés fait échouer les suivants, à juste titre. On repart donc
// d'une plateforme propre, et on la rend propre à la fin — y compris si un
// test échoue en cours de route.
test.beforeAll(() => {
  removeTestTenants()
})
test.afterAll(() => {
  removeTestTenants()
})

test.describe('administration plateforme', () => {
  test.beforeAll(() => {
    ensurePlatformAdmin()
  })

  test('pilote la ressource rare, convertit un prospect et refuse le dépassement', async ({
    page,
  }) => {
    test.setTimeout(180000)
    await loginAsPlatformAdmin(page)

    // --- 1. L'état du pool partagé, visible en permanence -------------------
    await page.goto('/admin/plateforme')
    await expect(
      page.getByRole('heading', { name: 'Administration de la plateforme' })
    ).toBeVisible()
    // Délai explicite : la page agrège six appels, et cette suite lance en
    // parallèle des commandes Django dans le conteneur, ce qui allonge le
    // premier rendu sur une machine chargée.
    await expect(page.getByText('Emplacements de surveillance continue')).toBeVisible({
      timeout: 15000,
    })
    // La formulation qui empêche le contresens le plus coûteux : ces plafonds
    // ne sont pas des quotas par client.
    await expect(
      page.getByText(/s’appliquent à la plateforme entière, pas à chaque client/)
    ).toBeVisible()

    // --- 2. Une demande de démonstration devient un client ------------------
    const suffix = uniqueSuffix()
    const company = `Prospect E2E ${suffix}`
    djangoShell(
      [
        'from apps.marketing.models import DemoRequest',
        `DemoRequest.objects.create(full_name='Camille E2E', company='${company}',`,
        `    email='prospect-${suffix}@example.com', role='Gérante')`,
      ].join('\n')
    )

    // La liste a été chargée à l'ouverture de la page : on la recharge après
    // avoir déposé la demande.
    await page.reload()
    await page.getByRole('tab', { name: /Demandes/ }).click()
    const card = page.locator('li', { hasText: company })
    await expect(card).toBeVisible()
    await card.getByRole('button', { name: 'Convertir en client' }).click()

    // Le client existe, avec son essai ouvert. On vérifie l'état durable —
    // la demande devenue « déjà cliente », puis la ligne dans les clients —
    // plutôt que la notification, qui s'efface d'elle-même.
    await expect(card.getByText('Déjà cliente')).toBeVisible()
    await page.getByRole('tab', { name: /Clients/ }).click()
    const row = page.locator('tr', { hasText: company })
    await expect(row).toBeVisible()
    await expect(row.getByText('Essai')).toBeVisible()

    // --- 3. Le dépassement est REFUSÉ, pas constaté après coup --------------
    // La plateforme est remplie avec de vrais abonnements jusqu'au plafond de
    // la licence : c'est l'état réel du jour où elle sera pleine.
    const [used, cap] = fillMonitoredSlotPool(suffix).split(' ')
    expect(used).toBe(cap)

    const secondCompany = `Prospect E2E bis ${suffix}`
    djangoShell(
      [
        'from apps.marketing.models import DemoRequest',
        `DemoRequest.objects.create(full_name='Dominique E2E', company='${secondCompany}',`,
        `    email='prospect-bis-${suffix}@example.com')`,
      ].join('\n')
    )

    await page.reload()
    await page.getByRole('tab', { name: /Demandes/ }).click()
    const blocked = page.locator('li', { hasText: secondCompany })
    await blocked.getByRole('button', { name: 'Convertir en client' }).click()

    // Le message doit dire ce qui reste disponible : sans cela, l'exploitant
    // ne sait pas s'il doit libérer un emplacement ou changer de palier.
    await expect(
      page.getByText(/plafond plateforme de \d+\. Il en reste \d+ disponible/)
    ).toBeVisible()

    // Et rien n'a été enregistré.
    const created = djangoShell(
      [
        'from apps.tenants.models import Tenant',
        `print(Tenant.objects.filter(name='${secondCompany}').count())`,
      ].join('\n')
    )
    expect(created).toBe('0')

    // On libère les emplacements dès que le refus est constaté : les tests
    // suivants (et la démonstration) ont besoin d'une plateforme respirable.
    removeFillerTenants(suffix)

    // --- 4. La santé de la plateforme --------------------------------------
    await page.getByRole('tab', { name: /Santé/ }).click()
    await expect(page.getByText('État des services')).toBeVisible()
    await expect(page.getByText('Base de données')).toBeVisible()

    // --- 5. Les clés sont décrites, jamais divulguées -----------------------
    await page.getByRole('tab', { name: /Configuration/ }).click()
    await expect(page.getByText('Clés et secrets')).toBeVisible()
    const configText = await page.locator('main').innerText()
    expect(configText).not.toMatch(/[A-Za-z0-9_-]{43}=/) // forme d'une clé Fernet

    // --- 6. L'administrateur n'est pas au-dessus de l'audit -----------------
    await page.getByRole('tab', { name: /Journal/ }).click()
    await expect(page.getByText('Journal consolidé')).toBeVisible()
    await expect(page.getByText(ADMIN_EMAIL).first()).toBeVisible()
  })
})

test.describe('client sur une offre limitée', () => {
  // Une inscription ouvre un essai de trois emplacements. Le jeu de démonstration
  // en engage déjà dix sur quinze : sans rendre au pool ce que les tests
  // précédents ont pris, l'inscription serait refusée — à juste titre.
  test.beforeEach(() => {
    removeTestTenants()
  })

  test('voit la fonctionnalité hors offre désactivée, avec l’offre qui la débloque', async ({
    page,
  }) => {
    test.setTimeout(180000)
    const suffix = uniqueSuffix()
    const company = `Client Limite ${suffix}`
    const email = `limite-${suffix}@example.com`

    await registerNewTenant(page, { companyName: company, email })

    // On place l'entreprise sur l'offre la plus basse, celle qui ne comprend
    // pas la synthèse d'exposition. Le but du test est ce que le CLIENT voit.
    djangoShell(
      [
        'from apps.tenants.models import Tenant',
        'from apps.billing.models import Plan, Subscription',
        `t = Tenant.objects.get(name='${company}')`,
        "s = Subscription.objects.get(tenant=t)",
        "s.plan = Plan.objects.get(code='veille')",
        "s.save(update_fields=['plan'])",
      ].join('\n')
    )

    await page.goto('/exposition')
    // La fonctionnalité n'est pas masquée : le client voit qu'elle existe…
    const locked = page.locator('[data-feature-locked="exposure_synthesis"]')
    await expect(locked).toBeVisible()
    await expect(locked).toHaveAttribute('aria-disabled', 'true')
    // …et sait ce qui la lui donnerait.
    await expect(page.getByText(/Compris à partir de l’offre Pilotage/).first()).toBeVisible()
  })

  test('conserve l’accès en lecture quand l’abonnement est suspendu', async ({ page }) => {
    test.setTimeout(180000)
    const suffix = uniqueSuffix()
    const company = `Client Suspendu ${suffix}`
    const email = `suspendu-${suffix}@example.com`

    await registerNewTenant(page, { companyName: company, email })
    djangoShell(
      [
        'from apps.tenants.models import Tenant',
        'from apps.billing.models import Subscription',
        `t = Tenant.objects.get(name='${company}')`,
        's = Subscription.objects.get(tenant=t)',
        's.status = Subscription.Status.SUSPENDED',
        "s.save(update_fields=['status'])",
      ].join('\n')
    )

    // On ne prend jamais les données d'un client en otage : la lecture reste
    // ouverte, seules les analyses et la surveillance sont bloquées.
    await page.goto('/tableau-de-bord')
    await expect(page.getByRole('heading').first()).toBeVisible()
    await expect(page.getByText(/Aucune entreprise associée/)).toHaveCount(0)

    const response = await page.evaluate(async () => {
      const access = localStorage.getItem('rssi.access')
      const tenantId = localStorage.getItem('rssi.tenantId')
      const r = await fetch('http://localhost:8000/api/v1/threat-intelligence/scans/', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${access}`,
          'X-Tenant-Id': tenantId,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      })
      return { status: r.status, body: await r.text() }
    })
    // 402 : l'abonnement ne permet pas l'opération — ce n'est ni un défaut de
    // droits (403) ni une panne.
    expect(response.status).toBe(402)
  })
})

test.describe('vitrine publique', () => {
  test('affiche la grille tarifaire servie par l’API', async ({ page }) => {
    await page.goto('/')
    await page.locator('#tarifs').scrollIntoViewIfNeeded()
    await expect(page.getByText('Souverain')).toBeVisible()
    await expect(page.getByText('Sur devis')).toBeVisible()
  })

  test('énonce ce que le service ne fait pas', async ({ page }) => {
    await page.goto('/securite-donnees')
    await expect(
      page.getByRole('heading', { name: /Sécurité et traitement des données/ })
    ).toBeVisible()
    await expect(page.getByText('Ce que le service ne fait pas')).toBeVisible()
  })
})
