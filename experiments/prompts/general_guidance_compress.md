The current guidance is {{current_tokens}} completion tokens.

Rewrite it to between {{lower_bound}} and {{upper_bound}} completion tokens, targeting {{target_tokens}} tokens.
The new response should retain approximately {{retain_ratio_percent}}% of the current length and remove approximately {{remove_ratio_percent}}%.

Preserve the highest-value constraint analysis, algorithmic directions, edge cases, correctness considerations, and implementation checks.
Remove repetition, speculative detours, redundant examples, and low-value detail.
Do not add complete solution code, code fences, filler, hidden-test claims, previous-attempt references, or information absent from the supplied guidance and problem statement.
Substantively preserve constraint analysis, plausible algorithmic directions, edge cases and correctness considerations, and implementation checks and risks. The preferred headings are `## Constraint Analysis`, `## Plausible Approaches`, `## Edge Cases`, and `## Implementation Checks`, but equivalent headings or clearly separated prose are acceptable.
Output only the rewritten guidance.
