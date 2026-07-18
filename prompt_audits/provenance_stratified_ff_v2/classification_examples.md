# Classification examples

- Raw standardized final error type, exact submitted code, its SHA-256, and exact raw excerpts are `DIRECT_FACT`.
- “The code contains nested loops” and a short reproducible complexity analysis produced by the organizer are `EVIDENCE_GROUNDED_INFERENCE`, never facts.
- Every Teacher claim, including algorithm, proof, complexity, attempted method, and failure diagnosis, is `LOW_CONFIDENCE_HYPOTHESIS`.
- “The quadratic complexity caused the timeout” is a low-confidence causal hypothesis because the final error type cannot identify a unique cause.
- Ambiguity fails closed to `LOW_CONFIDENCE_HYPOTHESIS`.
