The complete source material is {{source_tokens}} completion tokens. Its observed prior outcomes are {{previous_outcomes}}.

Perform an editing-only compression so the result is between {{lower_bound}} and {{upper_bound}} completion tokens, targeting {{target_tokens}} tokens.
Retain approximately {{retain_ratio_percent}}% of the source length and remove approximately {{remove_ratio_percent}}%.

Preserve all four substantive semantic regions: constraint analysis; plausible algorithmic directions; correctness and edge cases; and implementation checks and risks. Soft section token budgets are {{section_budget}}. Structural paragraph budgets are {{paragraph_budget}}.
Preferred headings are `## Constraint Analysis`, `## Algorithmic Directions`, `## Correctness and Edge Cases`, and `## Implementation Checks`; exact titles are not a validity condition. Every semantic region is mandatory and must retain substantive, complete content.
You may delete repetition or low-value detail within sections, merge overlapping passages within the same section, abbreviate or condense wording, and reorder existing material only within its original section when needed for coherence.
Use only content units present in the validated blueprint and complete source. Do not introduce any new content. In particular, do not add facts, claims, algorithmic directions, reasoning steps, examples, edge cases, implementation advice, solution code, pseudocode, code fences, filler, hidden-test claims, or previous-attempt references that are absent from the source guidance.
{{revision_feedback}}
Complete the final section naturally before the output capacity is reached. The output capacity is not the target length.
Output only the edited guidance.
