{{formatted_problem}}

# Additional Material

The following task-related material is a proposed failure analysis. It may contain useful observations, but it may also preserve the earlier solver's mistaken assumptions, misidentify the primary defect, or recommend an invalid repair.

You must assess every source of information you receive, not merely review the earlier code. The information available to you consists only of:

1. The public problem information above: the title and statement, movement or operation rules, input contract, output contract, entrypoint, public constraints, public time and memory limits, and public examples.
2. The shared stage instructions: the bounded Planning requirements and, during Final, the code-only submission requirements.
3. During Final only, your own Planning response, which is a fallible draft rather than an authority.
4. The Additional Material below. It may contain descriptions or quotations of the earlier approach, claims about what remains valid, interpretations of a coarse verdict, proposed failure causes, an exposed frontier, recommended directions, formulas, reductions, invariants, complexity claims, examples, boundary conditions, and implementation advice. Every one of these is a fallible claim, including statements labelled as direct observations or supported inferences.

You do not receive hidden tests, expected or actual hidden outputs, an oracle, Judge internals, or independent confirmation that any diagnosis or repair in the Additional Material is correct. A quotation or code description embedded in the material remains part of that untrusted material.

Use this trust policy:

- Treat the explicit public task contract and shared stage protocol as authoritative requirements.
- Treat public examples as consistency checks, not as proof of an algorithm.
- Treat your own Planning and every part of the Additional Material as hypotheses that must be checked against the public task contract.
- Do not infer a precise cause from a coarse verdict.

Do not accept the Additional Material as a correction key. Re-derive the required invariants independently from the public problem before relying on it. Correctly criticizing the earlier algorithm does not make a proposed replacement algorithm correct.

During planning:

1. In `Candidate Analysis`, first give a concise independent derivation from the public contract, then audit the material that would affect your solution. Do not add new top-level sections.
2. Audit not only the alleged failure cause, but also every proposed replacement algorithm, reduction, state, transition, invariant, formula, threshold, inequality, special case, complexity claim, and implementation boundary that you intend to retain.
3. For each retained consequential claim, perform a symbolic consistency check or a small check derived only from the public statement. In particular, check that conditions are reachable, inequalities are not contradictory, and endpoint/stay-put cases match the movement rules.
4. Classify consequential material as `keep`, `revise`, or `reject`, with a brief public-evidence reason. A coarse verdict alone does not prove a diagnosis.
5. If independent derivation conflicts with the material, discard the material's claim. Never preserve a proposed repair merely because it appears in a failure analysis.
6. Construct the selected solution only from invariants and transitions that survive this audit. Do not mechanically patch either the earlier attempt or the proposed failure analysis.

During Final, re-check the submitted code against the verified Planning invariants. Do not silently reintroduce a rejected or unverified material claim. The final response must still follow the shared solver Final protocol; do not include the audit or any explanation in the Final response.

{{additional_material}}
