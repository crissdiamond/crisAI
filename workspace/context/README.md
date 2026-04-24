# Synthetic Context Corpus v2

This corpus is designed to test the crisAI `context` agent.

It deliberately requires cross-retrieval across folders. The answer to a design prompt should not be available from a single file or from filenames alone.

## Structure

- reference: background context
- patterns: reusable architecture patterns
- standards: stronger guidance and rules
- designs: previous examples and precedents
- notes: informal discovery material

## Intended test prompt

Draft a solution design recommendation for a recurring Power BI dashboard currently sourced from manually maintained Excel files. The recommendation should decide whether Power BI should connect directly to the files or whether the files should be ingested into the data platform first. Include governance, lineage, ownership, and data quality considerations.

## Expected retrieval behaviour

A good context agent should retrieve from:
- notes for the current problem
- standards for mandatory constraints
- patterns for the recommended approach
- designs for precedent
- reference for platform and domain background
