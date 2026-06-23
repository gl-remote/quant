import '@testing-library/jest-dom';
import { vi, beforeEach } from 'vitest';

global.fetch = vi.fn();

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

global.ResizeObserver = ResizeObserverMock;

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
});

const originalGetComputedStyle = window.getComputedStyle;
window.getComputedStyle = ((elt: Element, pseudoElt?: string | null) => {
  if (pseudoElt) {
    return originalGetComputedStyle(elt);
  }
  return originalGetComputedStyle(elt);
}) as typeof window.getComputedStyle;

beforeEach(() => {
  vi.clearAllMocks();
});