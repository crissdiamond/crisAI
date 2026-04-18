User request:
{message}

Discovery findings:
{discovery_text}

Task:
Produce the best possible architecture, design, or documentation response for the user's request.

Rules:
- Treat the discovery findings as the authoritative retrieval result for this run.
- Do not invent or reopen file paths unless discovery explicitly identified them.
- If discovery found no reliable sources, say so and work only from the verified findings provided.
- Where a diagram would help, generate Mermaid.
