// Polyfill Web APIs for jsdom environment
// Node 22+ has these built-in, but jsdom doesn't expose them
const { TextEncoder, TextDecoder } = require("util");

if (typeof globalThis.TextEncoder === "undefined") {
  Object.assign(globalThis, { TextEncoder, TextDecoder });
}
