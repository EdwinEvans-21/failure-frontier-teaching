# Minimal Failure Lineage v1

This protocol tests whether direct-parent failure inheritance adds value beyond an equal number of independent solver opportunities. Generation 0 is a hash-locked Teacher-failure episode and is never resampled. Generations 1 through 5 each use at most one Planning call, one Final call, one extraction, and one Judge submission.

The three conditions are independent restart, direct-parent code plus standardized verdict, and the same direct-parent material plus the currently frozen Flat FF. The Flat condition has extra generation calls and a longer context, so comparisons are opportunity-balanced but neither token-balanced nor model-call-balanced.

Only direct-parent artifacts may be rendered. Parent and root hashes, prompt hashes, model parameters, renderer version, sandbox identity, stage completion, and condition rotation are resume invariants. A missing extractable code terminates chain conditions but remains in the system-level denominator; an independent restart continues. Flat FF generation or validation failure terminates the Flat treatment without fallback. Infrastructure interruption can resume the same run ID and must not resample completed stages.

The primary comparison is code-and-verdict inheritance versus independent restart. The secondary comparison is Flat FF inheritance versus code-and-verdict inheritance. A later AC does not imply changed model weights or intrinsic capability: it may reflect memory, repeated sampling, search, or iteration. Results sharing a problem and frozen root are clustered observations.

## Lineage-only Flat add-on v2

`code_verdict_flat_ff_chain_v2` is a separately versioned treatment. It keeps
the byte-identical `code_verdict_chain_v1` instruction, code block, and verdict
block, then adds one `Direct-Parent Flat Failure Analysis` block rendered by
`lineage_flat_analysis_renderer_v1`.

The renderer consumes the validated structured record and preserves accepted
substantive entries in registry order. It does not parse historical rendered
Markdown, invoke another model, emit confidence-tier framing, or reproduce the
complete parent code and raw Teacher sources. The validated record, add-on, and
complete model-visible payload have separate artifacts and SHA-256 identities.
Any record, renderer-version, parent, add-on, or complete-payload drift fails
closed instead of falling back to Code + Verdict.

The historical `code_verdict_flat_ff_chain_v1` condition and
`flat_provenance_payload_renderer_v2` remain unchanged.
