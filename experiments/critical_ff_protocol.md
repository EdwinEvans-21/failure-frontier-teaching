# Critical Failure-Frontier Paired Protocol

## Purpose

The existing `failure_frontier` condition supplies a model-generated analysis of an earlier Teacher failure. That analysis is evidence, not ground truth. It can preserve the Teacher's assumptions, focus on a superficial defect, or recommend an invalid repair.

The opt-in `critical_failure_frontier` condition tests whether an explicit verification protocol helps a Student use the same Failure Frontier more reliably. It does not replace or rewrite the Failure Frontier.

## Conditions

For every Teacher-failure episode, the naive and critical Students receive byte-identical Failure-Frontier material:

- `failure_frontier`: the existing material framing;
- `critical_failure_frontier`: the same material plus instructions to re-derive public invariants, classify claims by evidential support, verify alleged failure causes, and revise or reject unsupported feedback.

Both Students use the same model, public problem statement, Planning and Final budgets, two-stage solver protocol, code extraction, Judge, and one-submission limit. Their only intended treatment difference is the user-prompt framing around the shared material.

Baseline and General Guidance remain present as contextual controls. Existing configs omit `critical_failure_frontier` and retain their original three-condition behavior. The opt-in configuration is `experiments/configs/expanded_critical_ff_v1.yaml`.

## Isolation and ordering

- Each Student starts from a fresh context.
- No Student sees another Student's Planning, Final, code, or verdict.
- Naive and critical Students receive the exact same FF content hash.
- The four Student execution conditions are deterministically permuted from `run_id + problem_id` to reduce fixed-order confounding.
- Teacher-success episodes give every Student identical Success Teaching Material and identical framing. They are excluded from naive-versus-critical FF analysis.

## GG fallback and eligibility

Strict GG acceptance still requires a complete, semantically valid response
whose API completion-token count is within the registered interval. If all
strict attempts fail, the runner selects the safe generated candidate with the
smallest absolute completion-token distance from the FF target; ties use the
earliest version. Format validity and interval membership do not filter this
fallback, but forbidden content remains excluded.

- A complete fallback inside the token interval is a formal episode even when
  the GG section/semantic format is invalid. It is separately recorded as
  `formal_format_exception`; strict token-match failure remains visible.
- A selected fallback outside the interval, or a truncated/incomplete selected
  fallback, is recorded as `exploratory_closest_fallback`.
- A run with no safe selectable GG candidate remains invalid.

A paired naive-versus-critical observation requires:

A paired naive-versus-critical observation requires:

- a valid Teacher-failure episode;
- a non-truncated Failure Frontier below its output limit;
- exactly one Planning, one Final, and one coarse verdict for both FF Students;
- no infrastructure error or manual resampling;
- identical recorded FF material hashes.

The current opt-in runner also retains GG generation and the existing strict episode eligibility policy. If GG generation makes the whole episode invalid, the episode is not included in the paired estimate. This is a known design limitation to revisit before a dedicated Critical-FF-only experiment.

## Descriptive outcomes

Report paired counts and problem IDs for:

- both AC;
- naive FF only AC;
- Critical FF only AC;
- neither AC;
- the complete naive-to-critical verdict transition table.

Also inspect whether Critical FF changes the selected invariant, algorithm family, or implementation checks. With one sample per problem, these are exploratory observations rather than causal or statistically significant conclusions.

## Pilot recommendation

Before a formal batch, run a mock chain and a small real smoke on known diagnostic patterns such as:

- feedback that correctly identifies a missing global term;
- feedback that focuses on a superficial runtime defect while preserving an invalid algorithm;
- feedback that states an invariant correctly but implements a contradictory formula;
- feedback that recommends a valid global method after a failed local greedy method.

Do not reuse the earlier expanded batch responses as new model inputs. They may be used only for offline motivating analysis and for selecting preregistered diagnostic categories.
