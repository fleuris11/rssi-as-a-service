import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    // e2e/ contient des specs Playwright : les deux suites cohabitent dans
    // le même dossier frontend, il faut donc exclure explicitement l'une de
    // l'autre (sinon Vitest tente de lancer les tests Playwright).
    include: ['src/**/*.test.{js,jsx}'],
    exclude: ['e2e/**', 'node_modules/**'],
    // jsdom sous Windows est lent : `userEvent.type` frappe caractère par
    // caractère et provoque un rendu à chaque touche, ce qui dépasse
    // régulièrement les 5 s par défaut sur un formulaire de six champs. Le
    // délai est relevé plutôt que les tests réécrits en `fireEvent`, qui
    // contournerait précisément le pipeline de saisie qu'on veut exercer
    // (c'est lui qui avait révélé le vol de focus des modales).
    testTimeout: 20000,
  },
})
