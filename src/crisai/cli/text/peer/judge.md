User request:
{message}

Discovery findings (if any):
{discovery_text}

Challenge:
{challenger_text}

Refined draft:
{refiner_text}

Task:
Decide whether the refined answer is good enough, needs refinement, or needs structural rework.

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
- decision: accept / revise / rework
- reason
- remaining issues, if any
