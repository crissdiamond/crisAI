import React from "react";
import { parseInlineMarkdown, parseMarkdownBlocks, type MarkdownInlineToken } from "../runDisplay.js";

export function MarkdownContent({ content }: { content: string }) {
  return <div className="markdown-content">{renderMarkdownBlocks(content)}</div>;
}

export function renderMarkdownBlocks(content: string): React.ReactNode[] {
  return parseMarkdownBlocks(content).map((block, index) => {
    if (block.type === "heading") {
      const Tag = `h${block.level}` as React.ElementType;
      return <Tag key={index}>{renderInlineMarkdown(block.children)}</Tag>;
    }
    if (block.type === "code") {
      return (
        <pre key={index} className="markdown-code">
          <code>{block.value}</code>
        </pre>
      );
    }
    if (block.type === "list") {
      return (
        <ul key={index}>
          {block.items.map((item, itemIndex) => (
            <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>
      );
    }
    if (block.type === "table") {
      return (
        <div key={index} className="markdown-table-scroll">
          <table>
            <thead>
              <tr>
                {block.headers.map((header, headerIndex) => (
                  <th key={headerIndex}>{renderInlineMarkdown(header)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {block.headers.map((_, cellIndex) => (
                    <td key={cellIndex}>{renderInlineMarkdown(row[cellIndex] ?? [])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    return <p key={index}>{renderInlineMarkdown(block.children)}</p>;
  });
}

export function renderInlineMarkdown(tokens: MarkdownInlineToken[]): React.ReactNode[] {
  return tokens.map((token, index) => {
    if (token.type === "strong") {
      // Parse inside bold so a bold-wrapped link (**[name](url)**) still renders
      // as a clickable link rather than literal `[name](url)` text.
      return <strong key={index}>{renderInlineMarkdown(parseInlineMarkdown(token.value))}</strong>;
    }
    if (token.type === "code") {
      return <code key={index}>{token.value}</code>;
    }
    if (token.type === "link") {
      // Parse inside link text so a bolded label ([**name**](url)) still renders.
      return (
        <a key={index} href={token.href} target="_blank" rel="noreferrer">
          {renderInlineMarkdown(parseInlineMarkdown(token.value))}
        </a>
      );
    }
    return token.value;
  });
}
