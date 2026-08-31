import "@testing-library/jest-dom/vitest";

if (!window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = () => {};
}

// Node 22+ ships a built-in `localStorage`/`sessionStorage` global. Vitest's
// jsdom environment deliberately leaves globals like this alone when they
// already exist on `globalThis`, so `window.localStorage` (an alias for
// `globalThis.localStorage`) resolves to Node's half-initialized Web Storage
// object instead of jsdom's, and calls like `.clear()` blow up. Vitest stashes
// the real jsdom instance at `globalThis.jsdom`; pull the working
// implementation from there and force it onto the global scope.
const jsdomWindow = (globalThis as unknown as { jsdom?: { window: Window } }).jsdom?.window;
if (jsdomWindow) {
  for (const key of ["localStorage", "sessionStorage"] as const) {
    Object.defineProperty(globalThis, key, {
      value: jsdomWindow[key],
      configurable: true,
      writable: true,
    });
  }
}
