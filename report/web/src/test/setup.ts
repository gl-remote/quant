import '@testing-library/jest-dom';
import { vi, beforeEach } from 'vitest';

global.fetch = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});