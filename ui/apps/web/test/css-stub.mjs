// Test-only loader hook. Component modules (e.g. the Toast UI MarkdownEditor)
// import CSS for side effects, which Node's ESM loader cannot handle. The web
// build is bundled by Vite, which understands CSS imports; under node:test we
// only exercise logic, so map every `.css` import to an empty module.
import { register } from "node:module";

register(new URL("./css-stub-hooks.mjs", import.meta.url));
