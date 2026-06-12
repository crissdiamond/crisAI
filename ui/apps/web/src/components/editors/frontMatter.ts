// YAML front-matter split/join helpers for the Markdown editor.
//
// Toast UI has no front-matter awareness and normalises whitespace on
// getMarkdown(), so the front-matter block must be carved off before the body
// reaches the WYSIWYG editor and re-attached byte-for-byte on the way out. A
// manual split is used deliberately instead of a library such as gray-matter:
// gray-matter pulls in a Buffer dependency that needs a Vite polyfill, whereas
// these pure functions add no dependency and are trivially unit-testable.

// Matches a leading YAML front-matter block: an opening `---` line, any content
// (non-greedy), a closing `---` line, and the trailing newline. The captured
// block therefore includes both `---` delimiters and the newline after the
// closing delimiter, so the body is exactly the remainder of the file.
const FRONT_MATTER_PATTERN = /^---\r?\n[\s\S]*?\r?\n---[ \t]*\r?\n?/;

export interface SplitMarkdown {
  /**
   * The raw front-matter block including both `---` delimiters and the trailing
   * newline, or "" when the text has no leading front-matter block.
   */
  frontMatter: string;
  /** The remainder of the text after the front-matter block. */
  body: string;
}

/**
 * Splits a leading YAML front-matter block off the front of `text`.
 *
 * When `text` starts with a `---` line and has a matching closing `---` line,
 * `frontMatter` is the entire raw block (delimiters and trailing newline
 * included) and `body` is everything after it. Otherwise `frontMatter` is ""
 * and `body` is the original text unchanged.
 */
export function splitFrontMatter(text: string): SplitMarkdown {
  const match = FRONT_MATTER_PATTERN.exec(text);
  if (!match) {
    return { frontMatter: "", body: text };
  }
  return { frontMatter: match[0], body: text.slice(match[0].length) };
}

/**
 * Recombines a front-matter block and body into a single document.
 *
 * This is a byte-exact concatenation: `joinFrontMatter(splitFrontMatter(x))`
 * reproduces `x` exactly, so an untouched front-matter block round-trips
 * unchanged.
 */
export function joinFrontMatter(frontMatter: string, body: string): string {
  return frontMatter + body;
}
