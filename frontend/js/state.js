// Minimal cross-cutting application state. Pages read/write here instead of
// stashing values on the global window object.

export const appState = {
  currentRoute: "nifty",
};
