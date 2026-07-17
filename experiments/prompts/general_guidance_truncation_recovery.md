The previous material render exhausted the full output capacity and was unusable. Its reported completion token count was {{previous_candidate_tokens}}.

This is a truncation-recovery response. Write between {{lower_bound}} and {{upper_bound}} completion tokens, targeting {{target_tokens}} tokens.

Do not perform any new reasoning or algorithm search. Use only the validated blueprint. {{deduplication_instruction}}

Produce exactly four compact semantic sections, exactly once and in this order:

## Constraints
## Approaches
## Correctness
## Implementation

Use the deterministic section budgets {{section_budget}} and paragraph budgets {{paragraph_budget}}. Do not exceed the paragraph or sentence caps recorded there. Use at most two algorithmic directions total.

Every section must contain substantive content. Do not narrate your thought process. Do not introduce any approach not present in the blueprint. Do not include code, pseudocode, or code fences. Do not refer to previous attempts, submitted code, verdicts, failure analyses, hidden tests, Judge information, oracle, or checker.

Finish all four sections. The output capacity is not the target length. Output only the compact guidance.
