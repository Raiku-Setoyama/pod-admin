import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import Module from 'node:module'

// Patch Node's require to return vitest's ESM mock for dual-package modules.
// vitest's vi.mock() only intercepts ESM imports (.mjs), but some tests
// use require() which resolves to CJS (.js). This patch looks up the
// mock module in vitest's executor cache using the "mock:" prefix.
const esmPathMap: Record<string, string> = {
  'swr': '/app/node_modules/swr/dist/index/index.mjs',
}
const originalRequire = Module.prototype.require;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(Module.prototype as any).require = function patchedRequire(id: string) {
  if (id in esmPathMap) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const mocker = (globalThis as any).__vitest_mocker__
    if (mocker?.executor?.moduleCache) {
      const mockKey = `mock:${esmPathMap[id]}`
      const cached = mocker.executor.moduleCache.get(mockKey)
      if (cached?.exports) return cached.exports
    }
  }
  return originalRequire.call(this, id)
}

// Cleanup after each test
afterEach(() => {
  cleanup()
})

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}))

// Mock pointer capture methods for Radix UI Select
if (typeof Element.prototype.hasPointerCapture === 'undefined') {
  Element.prototype.hasPointerCapture = vi.fn().mockReturnValue(false)
}
if (typeof Element.prototype.setPointerCapture === 'undefined') {
  Element.prototype.setPointerCapture = vi.fn()
}
if (typeof Element.prototype.releasePointerCapture === 'undefined') {
  Element.prototype.releasePointerCapture = vi.fn()
}

// Mock scrollIntoView for Radix UI components
if (typeof Element.prototype.scrollIntoView === 'undefined') {
  Element.prototype.scrollIntoView = vi.fn()
}

// jsdom does not implement object URLs (used for image previews)
if (typeof URL.createObjectURL === 'undefined') {
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
}

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}))

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})
