import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
const storedValues = new Map<string, string>();
const storage: Storage = {
	get length() { return storedValues.size; },
	clear: () => storedValues.clear(),
	getItem: key => storedValues.get(key) ?? null,
	key: index => [...storedValues.keys()][index] ?? null,
	removeItem: key => { storedValues.delete(key); },
	setItem: (key, value) => { storedValues.set(key, String(value)); },
};
vi.stubGlobal('localStorage', storage);
Object.defineProperty(window, 'localStorage', { configurable: true, value: storage });
class ResizeObserverAdapter {
	observe() {}
	unobserve() {}
	disconnect() {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverAdapter);
Object.defineProperty(window, 'ResizeObserver', { configurable: true, value: ResizeObserverAdapter });
Object.defineProperty(window, 'matchMedia', { writable: true, value: vi.fn().mockImplementation((query: string) => ({
	matches: false, media: query, onchange: null, addListener: vi.fn(), removeListener: vi.fn(),
	addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
})) });
afterEach(cleanup);