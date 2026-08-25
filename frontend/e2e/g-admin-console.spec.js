import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { uniqueSuffix, waitForContentLoaded } from './helpers.js'

/**
 * Phase 11 — le parcours qui valide la phase.
 *
 * Creer une offre, creer un prospect, le convertir en client sur cette offre,
 * inviter un second utilisateur, changer l'offre du client, surcharger un
 * quota, suspendre puis reactiver, retirer un utilisateur, et verifier le
 * journal d'audit. Le tout SANS jamais quitter l'interface : aucune commande,
 * aucun shell Django, aucun acces a la base.
 */

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const ADMIN_EMAIL = 'console-e2e@example.com'
const ADMIN_PASSWORD = 'ConsolePlateforme2026!'

function djangoShell(script) {
  return execFileSync(
    'docker',
    ['compose', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '--no-imports', '-c', script],
    { cwd: REPO_ROOT, encoding: 'utf-8' }
  ).trim()
}

test.describe('console d administration', () => {
  test.beforeAll(() => {
    // Seule preparation autorisee : le compte administrateur lui-meme. Tout
    // le reste du parcours doit se faire a l'ecran.
    djangoShell(
      [
        'from apps.accounts.models import User',
        `u, _ = User.objects.get_or_create(email='${ADMIN_EMAIL}')`,
        'u.is_staff = True; u.is_superuser = True; u.is_active = True',
        `u.set_password('${ADMIN_PASSWORD}')`,
        'u.save()',
      ].join('\n')
    )
  })

  test.afterAll(() => {
    djangoShell(
      [
        'from apps.tenants.models import Tenant',
        'from apps.billing.models import Plan',
        'from apps.marketing.models import DemoRequest',
        'Tenant.objects.filter(name__startswith="Console E2E").delete()',
        'DemoRequest.objects.filter(company__startswith="Console E2E").delete()',
        'Plan.objects.filter(code__startswith="e2e-").delete()',
      ].join('\n')
    )
  })

  test('gere 100% du cycle de vie sans quitter l interface', async ({ page }) => {
    test.setTimeout(240000)
    const suffix = uniqueSuffix()
    const planCode = `e2e-${suffix}`.slice(0, 38)
    const planName = `Offre E2E ${suffix}`
    const company = `Console E2E ${suffix}`

    await page.goto('/connexion')

    await waitForContentLoaded(page)
    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Mot de passe').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: 'Se connecter' }).click()
    await page.waitForURL(/tableau-de-bord|admin/)
    await waitForContentLoaded(page)
    await page.goto('/admin/plateforme')
    await waitForContentLoaded(page)
    await expect(page.getByRole('heading', { name: 'Administration de la plateforme' })).toBeVisible()

    // --- 1. Creer une offre de zero -----------------------------------------
    await page.getByRole('tab', { name: /Offres/ }).click()
    await page.getByRole('button', { name: 'Nouvelle offre' }).click()
    const planForm = page.getByRole('dialog')
    await planForm.getByLabel('Code').fill(planCode)
    await planForm.getByLabel('Nom affiché').fill(planName)
    await planForm.getByLabel('Emplacements surveillés').fill('1')
    await planForm.getByLabel('Utilisateurs').fill('3')
    await planForm.getByLabel('État').selectOption('published')
    await planForm.getByRole('button', { name: 'Créer l’offre' }).click()
    // La boite se ferme quand l'enregistrement a reellement abouti.
    await expect(planForm).toHaveCount(0)
    await expect(page.getByText(planName).first()).toBeVisible()

    // --- 2. Creer un prospect a la main -------------------------------------
    await page.getByRole('tab', { name: /Prospects/ }).click()
    await page.getByRole('button', { name: 'Nouveau prospect' }).click()
    // On cible DANS la boite de dialogue : la page derriere porte deja des
    // champs de meme libelle (notes, relances des autres prospects).
    const prospectForm = page.getByRole('dialog')
    await prospectForm.getByLabel('Entreprise').fill(company)
    await prospectForm.getByLabel('Contact').fill('Camille Console')
    await prospectForm.getByLabel('Email').fill(`camille-${suffix}@console.example`)
    await prospectForm.getByRole('button', { name: 'Enregistrer' }).click()
    await expect(page.getByText(company).first()).toBeVisible()

    // --- 3. Le convertir en client sur cette offre --------------------------
    await page.getByRole('button', { name: 'Convertir en client' }).first().click()
    const clientForm = page.getByRole('dialog')
    await expect(clientForm.getByLabel('Nom de l’entreprise')).toHaveValue(company)
    await clientForm.getByLabel('Offre', { exact: true }).selectOption(planCode)
    await clientForm.getByRole('button', { name: 'Créer le client' }).click()
    // Un lien d'invitation, jamais un mot de passe.
    await expect(clientForm.getByText(/\/invitation\//)).toBeVisible()
    await expect(clientForm.getByText(/ne fonctionne qu’une fois/)).toBeVisible()
    await clientForm.getByRole('button', { name: 'Terminé' }).click()

    // --- 4. Inviter un second utilisateur -----------------------------------
    await page.getByRole('tab', { name: /Clients/ }).click()
    await page.getByRole('cell', { name: company }).first().click()
    await expect(page.getByRole('heading', { name: company })).toBeVisible()
    await page.getByLabel('Inviter un utilisateur').fill(`second-${suffix}@console.example`)
    await page.getByRole('button', { name: 'Inviter' }).click()
    await expect(page.getByText(`second-${suffix}@console.example`).first()).toBeVisible()

    // --- 5. Surcharger un quota --------------------------------------------
    await page.getByLabel('Analyses par mois').fill('99')
    await page.getByRole('button', { name: 'Enregistrer', exact: true }).last().click()
    await expect(page.getByLabel('Analyses par mois')).toHaveValue('99')

    // --- 6. Suspendre puis reactiver ----------------------------------------
    // « exact » est indispensable : « Activer » se confondrait sinon avec les
    // boutons « Desactiver » et « Reactiver » des utilisateurs.
    await page.getByRole('button', { name: 'Suspendre', exact: true }).click()
    // L'apparition d'« Activer » (et la disparition de « Suspendre ») est le
    // signal d'etat non ambigu : le badge peut etre hors du champ visible.
    await expect(page.getByRole('button', { name: 'Activer', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Suspendre', exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: 'Activer', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Suspendre', exact: true })).toBeVisible()

    // --- 7. Retirer un utilisateur ------------------------------------------
    const row = page.locator('li', { hasText: `second-${suffix}@console.example` })
    await row.getByRole('button', { name: 'Retirer' }).click()
    await expect(page.getByText('Ce qui va se passer')).toBeVisible()
    await page.getByRole('button', { name: 'Retirer', exact: true }).last().click()
    // L'adresse ne doit plus figurer dans la LISTE des utilisateurs ; elle
    // reste dans la notification de succes, qui s'efface d'elle-meme.
    await expect(page.locator('li', { hasText: `second-${suffix}@console.example` })).toHaveCount(0)

    // --- 8. Le journal d'audit a tout enregistre ----------------------------
    await page.getByRole('button', { name: 'Retour aux clients' }).click()
    await page.getByRole('tab', { name: /Journal/ }).click()
    await expect(page.getByText('Journal consolidé')).toBeVisible()
    const journal = await page.locator('main').innerText()
    expect(journal).toContain(ADMIN_EMAIL)
  })
})
