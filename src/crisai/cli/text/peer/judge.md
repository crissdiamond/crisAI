User request:
{message}

Discovery findings (if any):
{discovery_text}

Challenge:
{challenger_text}

Refined draft:
{refiner_text}

Task:
Decide whether the refined answer is good enough.

Rules:
- Work only from the user request, optional discovery findings, critique, and refined answer.
- Do not invent new evidence.
- Be decisive.

Check:
- relevance to the request
- fidelity to the evidence
- whether major critique points were addressed
- whether the answer is clear, useful, and internally consistent

Output:
- decision: accept / revise
- reason
- remaining issues, if any
