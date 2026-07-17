The previous generation exhausted the full output capacity and was unusable.

This is a truncation-recovery response. Write between {{lower_bound}} and {{upper_bound}} completion tokens, targeting {{target_tokens}} tokens.

Do not perform open-ended exploration.

Produce exactly four compact Markdown sections, exactly once and in this order:

## Constraints
## Approaches
## Correctness
## Implementation

Use at most:
- 3 bullets per section
- 2 sentences per bullet
- 2 algorithmic directions total

Every section must contain substantive content. Do not narrate your thought process. Do not introduce alternatives after selecting the two directions. Do not include code or code fences. Do not refer to previous attempts, submitted code, verdicts, failure analyses, hidden tests, or Judge information.

Finish all four sections. The output capacity is not the target length. Output only the compact guidance.
