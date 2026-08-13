import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  // Les composants testés utilisent des minuteurs (masquage automatique du
  // secret) : on repasse en horloge réelle après chaque test pour qu'un test
  // ayant activé les faux minuteurs ne contamine pas le suivant.
  vi.useRealTimers()
})

// jsdom n'implémente ni le presse-papier ni scrollIntoView, utilisés par les
// composants sous test. Stubs minimaux : ce qui nous intéresse est que le
// composant les appelle, pas ce que fait le navigateur derrière.
Object.assign(navigator, {
  clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
})
Element.prototype.scrollIntoView = vi.fn()
