import assert from "node:assert/strict";
import test from "node:test";
import {
  joinFrontMatter,
  splitFrontMatter
} from "../src/components/editors/frontMatter.js";

test("front-matter splits off verbatim and rejoins byte-stable", () => {
  const original =
    "---\nkey: val\n---\n# Body\n\n```mermaid\nA-->B\n```\n";

  const { frontMatter, body } = splitFrontMatter(original);

  // Front-matter keeps both delimiters and the trailing newline.
  assert.equal(frontMatter, "---\nkey: val\n---\n");
  // Body is exactly the remainder, including the untouched mermaid fence.
  assert.equal(body, "# Body\n\n```mermaid\nA-->B\n```\n");
  // Recombining reproduces the original byte-for-byte.
  assert.equal(joinFrontMatter(frontMatter, body), original);
});

test("text without front-matter yields empty front-matter and untouched body", () => {
  const original = "# Just a heading\n\nNo front matter here.\n";

  const { frontMatter, body } = splitFrontMatter(original);

  assert.equal(frontMatter, "");
  assert.equal(body, original);
  assert.equal(joinFrontMatter(frontMatter, body), original);
});

test("CRLF front-matter block round-trips byte-stable", () => {
  const original = "---\r\nkey: val\r\n---\r\nBody line\r\n";

  const { frontMatter, body } = splitFrontMatter(original);

  assert.equal(frontMatter, "---\r\nkey: val\r\n---\r\n");
  assert.equal(body, "Body line\r\n");
  assert.equal(joinFrontMatter(frontMatter, body), original);
});

test("a body edit recombines with the original front-matter verbatim", () => {
  const original = "---\ntitle: Doc\n---\n# Old body\n";
  const { frontMatter } = splitFrontMatter(original);

  // Simulate Toast UI handing back a normalised/edited body.
  const editedBody = "# New body\n\nMore text.\n";

  assert.equal(
    joinFrontMatter(frontMatter, editedBody),
    "---\ntitle: Doc\n---\n# New body\n\nMore text.\n"
  );
});
