# Failure-Frontier Teaching Protocol — Baseline v1

Baseline ID: `failure-frontier-baseline-v1`

## 1. Objective and capability dimensions

The experiment measures where code-generating models fail, whether coarse
judge outcomes support repair, and whether non-leaking teaching feedback moves
the failure frontier.  It does not treat infrastructure failures or access to
hidden information as model capability.

The fixed problems are:

| Problem | Role | Primary capability |
| --- | --- | --- |
| LeetCode 9 | `sanity_control` | Basic implementation and strict return type |
| LeetCode 3988 | `medium_upper_construction_candidate` | Non-unique construction under a trusted checker |
| LeetCode 3980 | `medium_dp_candidate` | Linear dynamic programming and proof-guided state design |
| LeetCode 3312 | `hard_number_theory_candidate` | Divisor counting, inclusion-exclusion and binary-search boundaries |
| LeetCode 3962 | `hard_optimization_candidate` | Interval optimization and dynamic order statistics |

## 2. Experimental conditions

Every `(model, problem, condition, repetition)` is an independent run.

- `baseline`: one initial prompt and no repair feedback; measures raw ability.
- `verdict_feedback`: repair attempts receive only the sanitized model-view
  verdict, phase and coarse message.
- `teaching_feedback`: repair attempts receive the same model-view fields plus
  researcher-approved conceptual guidance that contains no case-specific data.

Do not compare conditions by continuing the same conversation.  Each run starts
from the original prompt template, a clean submission workspace and no code,
messages, summaries or tool state from another run.  A run must never inherit a
previous run's submission.

The following are recommended defaults, not established facts:

| Decision | Recommended default | Status |
| --- | --- | --- |
| Repetitions per condition | 3 for the main study; 2 for the pilot | Researcher confirmation required |
| Maximum attempts | 1 for `baseline`; 3 for feedback conditions | Researcher confirmation required |
| Model temperature | 0 when supported | Researcher confirmation required |
| Model/API seed | Fixed per run when supported | Researcher confirmation required |
| Public tests | Allow problem statement examples; expose only public model-view results | Researcher confirmation required |
| Local ordinary tests | Disallow model access; orchestration may run them for infrastructure validation | Researcher confirmation required |
| Feedback granularity | Coarse verdict first; conceptual teaching only in its named condition | Researcher confirmation required |

Any deviation must be recorded in the experiment configuration and must define
a distinct condition rather than silently changing an existing condition.

## 3. Attempt lifecycle and information boundary

1. Verify the baseline manifest before a run.
2. Materialize a clean copy of the initial prompt and empty submission template.
3. Ask the model for one complete submission.  Hash the exact prompt and source.
4. Run the configured public phase, if allowed, then the hidden phase according
   to the execution policy.
5. Persist an internal run record before issuing feedback.
6. If repair is permitted, render the feedback template only from model-view
   fields and approved teaching text, then request a fresh complete submission.
7. Stop on AC or a configured terminal condition.

The internal view is restricted to the trusted experiment process and may
contain counts, runtime, internal failure category and operational diagnostics.
The model view may contain only `verdict`, `phase` and a sanitized coarse
message, plus condition-approved conceptual teaching.  Never expose hidden
inputs, expected or actual values, oracle/checker data, case index, passed-case
progress, optimal witnesses, intermediate states, raw stdout/stderr or stack
traces derived from hidden cases.

The same prohibition applies to prompts, feedback, logs shown to the model,
research summaries used as later model context, and manual researcher hints.

## 4. Verdict and retry rules

- `ACCEPTED`: terminal success for that problem/run.
- `WRONG_ANSWER`, `RUNTIME_ERROR`, `TIME_LIMIT_EXCEEDED`,
  `MEMORY_LIMIT_EXCEEDED`, `SYNTAX_ERROR` and `INVALID_SUBMISSION`: model
  outcomes.  They consume an attempt and may receive only condition-allowed
  feedback.
- `INTERNAL_ERROR`, Docker daemon failure, image/build failure, host resource
  failure, network/API interruption before a complete response, and logging
  failure are infrastructure outcomes.  They do not count as model failures.
- Retry an infrastructure failure with the identical prompt/submission and
  configuration.  Set `retry_of` to the original record and do not increment
  the model attempt number.  An identical-submission infrastructure retry must
  preserve `submission_hash`.
- If a model response was completely received before a connection interruption,
  persist it once and retry only evaluation; do not ask the model again.
- Repeated infrastructure failure terminates the run as incomplete after the
  configured infrastructure retry limit; it is excluded from model-failure
  denominators and reported separately.

## 5. Termination

A run terminates on first AC, exhaustion of model attempts, unrecoverable
configuration/baseline mismatch, or exhaustion of infrastructure retries.
Researcher cancellation is recorded explicitly and is not converted into a
model verdict.  Attempts after AC are forbidden.

## 6. Reproducibility

Record the verified baseline ID, manifest hash, source commit, source dirty-worktree flag,
model ID/version, full condition configuration, prompt/submission hashes,
timestamps, verdict sequence and infrastructure retries.  Use the frozen tests,
image and templates.  Preserve raw internal records outside model-visible
context.  Do not regenerate formal tests during an experiment.

Random assignment and model seeds must be recorded.  If an API does not honor a
seed or exposes a mutable model alias, record that limitation and the provider's
exact model version when available.  Run order should be randomized or blocked
by problem/model using a pre-recorded experiment seed.

## 7. Failure-Frontier metrics

Report per problem, model and condition, with uncertainty over independent
repetitions:

- `pass@1`: fraction whose first model attempt is AC.
- Final AC rate within the configured attempt budget.
- Attempts to first AC, conditional on success, plus censored failures.
- Full verdict sequence for every run.
- Repair transition rates such as WA→AC, RE→AC and TLE→AC.
- Success probability after each feedback round.
- Cumulative wall time, model attempts and configured token/cost units to AC.
- Final failure category when AC is not reached.

Interpret these as four separate constructs: raw capability (`baseline`), repair
from coarse verdicts (`verdict_feedback`), repair from teaching feedback
(`teaching_feedback`), and invalid apparent improvement caused by hidden-data
leakage.  Any leakage event invalidates the affected run; it is not an AC gain.

## 8. Pilot protocol

Recommended pilot defaults are two repetitions per problem and condition,
`max_attempts=1` for baseline and 3 otherwise, fixed temperature 0 and recorded
seed when supported.  Run all five problems and all three conditions, but do not
use pilot outcomes as final performance estimates.

The pilot acceptance checklist is:

- every run validates against `run_record.schema.json`;
- prompt, submission and retry hashes are complete;
- model feedback contains no hidden fields or case-derived text;
- an intentionally interrupted orchestration can resume without duplicating an
  attempt or changing its submission hash;
- the same baseline verifies before and after the pilot;
- reference and representative verdicts remain stable under the frozen limits;
- infrastructure failures are excluded from model-failure metrics.

Researchers must confirm repetitions, attempt budgets, temperature/seed,
public-test visibility, local-test policy and teaching rubric before the main
study begins.

The manifest records `source_commit`, the commit containing all frozen judge
code and data.  Regenerating `baseline_manifest.json` is ignored by the source
dirty check.  Commit the generated manifest alone in a subsequent commit and
point the authoritative baseline tag at that manifest-only commit; the manifest
does not attempt the impossible self-reference of recording its own commit ID.
