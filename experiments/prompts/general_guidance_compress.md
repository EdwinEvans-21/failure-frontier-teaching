The source guidance is {{source_tokens}} completion tokens.

Rewrite it to between {{lower_bound}} and {{upper_bound}} completion tokens, targeting {{target_tokens}} tokens.
Retain approximately {{retain_ratio_percent}}% of the source length and remove approximately {{remove_ratio_percent}}%.

Preserve all four substantive components: constraint analysis; plausible algorithmic directions; correctness and edge cases; and implementation checks and risks.
Remove repetition and low-value detail, but do not collapse substantive sections or add new algorithmic directions.
Do not add complete solution code, code fences, filler, hidden-test claims, previous-attempt references, or information absent from the supplied guidance and problem statement.
The preferred headings are `## Constraint Analysis`, `## Plausible Approaches`, `## Edge Cases`, and `## Implementation Checks`, but equivalent headings or clearly separated prose are acceptable.
Complete the final section naturally before the output capacity is reached. The output capacity is not the target length.
Output only the rewritten guidance.
