Repair a compact General Guidance blueprint using only the public problem and the validation error codes below.

Validation error codes: {{validation_errors}}

Output strict JSON only: no Markdown, code fence, commentary, pseudocode, or solution code. Use exactly this schema and no extra keys:

{"constraints":[{"point":"string","importance":"string"}],"approaches":[{"name":"string","core_idea":"string","why_plausible":"string","main_risk":"string"}],"correctness":[{"claim":"string","check":"string"}],"implementation":[{"risk":"string","check":"string"}]}

Required item counts: constraints 2-4; approaches 1-2; correctness 2-4; implementation 3-6. Every field must be one concise, non-empty sentence. Fix only the reported schema or content-policy violations. Do not infer or reproduce the previous invalid response, introduce a new category, or discuss any previous solver, verdict, hidden test, Judge, oracle, or checker.
