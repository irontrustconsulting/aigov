// CSS custom properties are consumed directly (primitives.css, skin-*.css —
// see package.json "exports"); this module has no runtime-meaningful export
// today. It exists so @irontrust/tokens is a valid TS import target for any
// future token-shaped TS constant (e.g. a JS mirror of a token for canvas/
// non-DOM rendering).
export {};
