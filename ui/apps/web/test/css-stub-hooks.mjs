// Resolve/load hooks that turn any `.css` import into an empty ES module so
// component modules can be imported under node:test (Vite handles real CSS in
// the browser build). See css-stub.mjs.
export async function load(url, context, nextLoad) {
  if (url.endsWith(".css")) {
    return { format: "module", source: "export default {};", shortCircuit: true };
  }
  return nextLoad(url, context);
}
