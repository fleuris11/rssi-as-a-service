import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { auditAccessibility, uniqueSuffix, waitForContentLoaded } from './helpers.js'

/**
 * Proposer une formation a un client, depuis la console, sans commande.
 *
 * C'est exactement ce qui manquait : `attribuer_cours` n'etait appele que par
 * des commandes Django. Un module dont l'exploitant ne peut rien proposer n'est
 * pas un module, et un test unitaire de panneau ne dit pas si la route existe,
 * si les droits passent, et si l'ecran se recharge sur la reponse du serveur.
 *
 * Preparation autorisee : le compte d'exploitation, un client, et la
 * bibliotheque de cours — trois choses qu'aucun ecran ne sait creer.
 */

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const ADMIN_EMAIL = 'formations-e2e@example.com'
const ADMIN_PASSWORD = 'FormationsConsole2026!'
const CLIENT = `Formations E2E ${uniqueSuffix()}`

function djangoShell(script) {
  return execFileSync(
    'docker',
    ['compose', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '--no-imports', '-c', script],
    { cwd: REPO_ROOT, encoding: 'utf-8' }
  ).trim()
}

test.describe('console — formations', () => {
  test.beforeAll(() => {
    djangoShell(
      [
        'from django.core.management import call_command',
        'from apps.accounts.models import User',
        'from apps.tenants.services import create_tenant_with_owner',
        "call_command('seed_catalogue_formation', verbosity=0)",
        `u, _ = User.objects.get_or_create(email='${ADMIN_EMAIL}')`,
        'u.is_staff = True; u.is_superuser = True; u.is_active = True',
        `u.set_password('${ADMIN_PASSWORD}')`,
        'u.save()',
        "p, _ = User.objects.get_or_create(email='formations-e2e-client@example.com')",
        'p.is_active = True; p.save()',
        `create_tenant_with_owner(name='${CLIENT}', owner=p)`,
      ].join('\n')
    )
  })

  test.afterAll(() => {
    djangoShell(
      [
        'from apps.tenants.models import Tenant',
        // Par PREFIXE : le nom porte un suffixe tire au chargement du module,
        // donc un echec precedent laisserait son client derriere lui.
        "Tenant.objects.filter(name__startswith='Formations E2E ').delete()",
      ].join('\n')
    )
  })

  test('propose un cours a un client, puis le retire', async ({ page }) => {
    test.setTimeout(120000)
    const erreurs = []
    page.on('console', (message) => {
      if (message.type() === 'error') erreurs.push(message.text())
    })

    await page.goto('/connexion')
    await waitForContentLoaded(page)
    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Mot de passe').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: 'Se connecter' }).click()
    // On n'attend pas une URL d'arrivee : un compte d'exploitation sans
    // adhesion n'atterrit pas au meme endroit qu'un client, et c'est la
    // console qu'on vient voir.
    // 30 s : le hachage du mot de passe prend une dizaine de secondes sur une
    // machine chargee, et l'attente par defaut de 5 s se declenche avant.
    await expect(page.getByRole('button', { name: 'Déconnexion' })).toBeVisible({
      timeout: 30000,
    })
    await page.goto('/admin/plateforme')
    await waitForContentLoaded(page)

    await page.getByRole('tab', { name: /Formations/ }).click()
    await expect(page.getByRole('heading', { name: /Proposer des formations/ })).toBeVisible()

    // Rien n'est charge avant qu'un client soit choisi.
    await expect(page.getByText('Bibliothèque')).toHaveCount(0)

    await page.getByLabel('Client').selectOption({ label: CLIENT })
    await expect(page.getByText('Bibliothèque')).toBeVisible()

    const premier = page.getByRole('button', { name: 'Proposer' }).first()
    await premier.click()
    await expect(page.getByRole('button', { name: 'Retirer' }).first()).toBeVisible()

    await auditAccessibility(page)

    await page.getByRole('button', { name: 'Retirer' }).first().click()
    // Le message est le contrat : le retrait ne touche pas aux parcours.
    await expect(
      page.getByText('Cours retiré. Les salariés déjà inscrits terminent leur parcours.')
    ).toBeVisible()

    expect(erreurs).toEqual([])
  })
})
