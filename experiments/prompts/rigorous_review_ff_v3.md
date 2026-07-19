A previous model attempted this problem but did not pass the evaluator. This verdict establishes only that the submitted program failed. It does not by itself show that the Teacher's algorithm family, intended invariant, or individual claims are wrong.

You receive exactly the same shared failure materials as Direct FF.

Use this source-aware trust boundary:

* DIRECT_FACT contains raw objective records only.
* EVIDENCE_GROUNDED_INFERENCE contains reproducible but fallible model-generated analysis and is not guaranteed correct.
* LOW_CONFIDENCE_HYPOTHESIS contains all Teacher-generated natural language and unsupported organizer explanations. Confident wording does not increase reliability.

Selectively inherit the material. Examine only claims that materially affect the final algorithm, including state meaning, greedy or monotonicity assumptions, transitions, processing order, sweep invariants, signs, indices, initialization, termination, and complexity under the public constraints.

For each such claim, internally choose one of:

* RETAIN: the claim is supported or remains a valid candidate.
* MODIFY: a specific, locally justified correction is needed.
* REJECT: the claim is contradicted by sufficient evidence.
* UNRESOLVED: the available evidence is insufficient to accept or reject it.

Do not reject a claim merely because the Teacher submission failed, because the claim appears counterintuitive, or because you can imagine an unverified concern.

A REJECT decision must be supported by at least one of the following:

* a concrete counterexample consistent with the public problem;
* a contradiction with the submitted code or another direct fact;
* a derivation from the public constraints showing that the claim or complexity cannot hold;
* a clear proof that the relevant invariant, transition, ordering, or monotonicity property is false.

Apply the same evidentiary standard to your own objections and alternative explanations. A newly generated criticism is also a fallible hypothesis until it is checked.

If a claim cannot be disproved, do not permanently discard it. Keep it as an unresolved candidate when constructing the solution.

Before committing to the final algorithm, re-check the small number of retained, modified, and rejected claims that determine correctness. In particular, verify that every rejected candidate was rejected for an actual contradiction rather than uncertainty, unfamiliarity, or the Teacher's verdict.

Do not review every sentence or produce a Teacher-criticism report. Use the checked claims to construct one coherent, correct, and efficient solution.
