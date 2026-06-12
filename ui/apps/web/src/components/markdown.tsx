import React from "react";
import { parseMarkdownBlocks, type MarkdownInlineToken } from "../runDisplay.js";

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
      return <strong key={index}>{token.value}</strong>;
    }
    if (token.type === "code") {
      return <code key={index}>{token.value}</code>;
    }
    return token.value;
  });
}
