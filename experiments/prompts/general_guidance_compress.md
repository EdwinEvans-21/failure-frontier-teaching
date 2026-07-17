The current guidance is {{current_tokens}} completion tokens.

Rewrite it to between {{lower_bound}} and {{upper_bound}} completion tokens, targeting {{target_tokens}} tokens.
The new response should retain approximately {{retain_ratio_percent}}% of the current length and remove approximately {{remove_ratio_percent}}%.

Preserve the highest-value constraint analysis, algorithmic directions, edge cases, correctness considerations, and implementation checks.
Remove repetition, speculative detours, redundant examples, and low-value detail.
Do not add code, filler, hidden-test claims, previous-attempt references, or information absent from the supplied guidance and problem statement.
Keep all four required section headings complete.
Output only the rewritten guidance.
