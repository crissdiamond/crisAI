# crisAI Context Knowledge Structure

## Purpose

This folder contains the local knowledge that the `context` agent can use to retrieve information and prepare useful context for downstream agents, especially design-related agents.

The goal is not to force every document into a strict template. Many useful documents already exist and may not contain rich metadata. Instead, the first layer of meaning comes from the folder where a document is placed.

## Root folder

```text
workspace/context
```

Only documents placed under this folder should be considered part of the local context knowledge base.

## Folder structure

```text
workspace/context/
  reference/
  patterns/
  standards/
  designs/
  notes/
```

## Folder semantics

### reference

Use this folder for stable background information.

Examples:
- strategy extracts
- system descriptions
- domain background
- copied reference material
- useful source documentation

The `context` agent should treat this material as background knowledge.

### patterns

Use this folder for reusable architecture, design, integration, data, or delivery patterns.

Examples:
- medallion architecture pattern
- API publishing pattern
- data product pattern
- solution design pattern
- MCP server pattern

The `context` agent should treat this material as reusable guidance.

### standards

Use this folder for rules, principles, conventions, and mandatory approaches.

Examples:
- naming standards
- modelling standards
- integration standards
- security principles
- data governance requirements

The `context` agent should treat this material as stronger guidance than notes or general reference material.

### designs

Use this folder for previous, current, or draft solution designs.

Examples:
- completed solution designs
- design options
- architecture decision notes
- example design documents
- draft designs used as precedent

The `context` agent should treat this material as examples or precedents, not automatically as mandatory standards.

### notes

Use this folder for informal or temporary knowledge.

Examples:
- meeting notes
- working thoughts
- rough analysis
- discovery notes
- investigation outputs

The `context` agent should treat this material as useful but less authoritative than standards, patterns, or designs.

## Initial document format

For the first version, plain text files are enough.

Supported initial format:

```text
.txt
```

Markdown files may also be used later if useful, but they are not required.

## Filename convention

Use clear, descriptive filenames in lowercase, with words separated by hyphens.

Good examples:

```text
student-data-access-protocol.txt
fabric-medallion-pattern.txt
sits-course-data-notes.txt
solution-design-revenue-recognition.txt
mcp-server-pattern.txt
```

Avoid vague filenames such as:

```text
notes.txt
document1.txt
draft.txt
misc.txt
```

## Authority model

The folder where a file is stored gives the agent a first indication of how strongly to rely on it.

Recommended authority order:

1. `standards` - strongest guidance
2. `patterns` - reusable guidance
3. `designs` - examples and precedents
4. `reference` - background knowledge
5. `notes` - informal or weakly validated knowledge

This does not mean that lower-authority material should be ignored. It means the agent should be careful when using it to support design recommendations.

## Expected agent behaviour

The `context` agent should:

1. Search inside `workspace/context`.
2. Use the folder path as metadata.
3. Prefer `standards` and `patterns` when looking for rules or reusable guidance.
4. Use `designs` when looking for precedent or examples.
5. Use `reference` for background understanding.
6. Use `notes` carefully and label them as informal context when relevant.
7. Return extracted context in a structured way for downstream agents.

## Out of scope for now

This structure does not require:

- embeddings
- a vector database
- mandatory document templates
- rich metadata files
- document rewriting
- complex indexing

Those capabilities can be added later if the simple folder-based approach proves useful.

## Design principle

Start with a simple and explainable knowledge structure.

The first version should help crisAI retrieve useful context from local documents without requiring a heavy content migration or a complex RAG pipeline.
