The source guidance is {{source_tokens}} completion tokens.

Rewrite it to between {{lower_bound}} and {{upper_bound}} completion tokens, targeting {{target_tokens}} tokens.
The new response should be approximately {{expand_ratio_percent}}% longer.

Add useful detail about constraint implications, plausible algorithmic alternatives, correctness considerations, edge cases, and implementation risks.
Do not repeat existing points, add filler, generate complete solution code or code fences, or refer to previous attempts, judge results, failure analyses, or hidden tests.
Preserve exactly these four Markdown sections, exactly once and in this order: `## Constraint Analysis`, `## Algorithmic Directions`, `## Correctness and Edge Cases`, and `## Implementation Checks`. Every section is mandatory and must contain substantive, complete content. Do not delete, rename, merge, or leave any required section empty.
Complete the final section naturally before the output capacity is reached. The output capacity is not the target length.
Output only the expanded guidance.
