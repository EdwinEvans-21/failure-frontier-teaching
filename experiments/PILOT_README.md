# Failure-Frontier Teaching Pilot v1

This module runs the minimal five-problem pilot above the frozen
`failure-frontier-baseline-v2` judge. It does not change problem statements,
oracles, tests, resource limits, Docker isolation, comparisons, or verdict
generation. The baseline manifest is verified before every run.

## Configuration

Copy or edit `experiments/configs/pilot_v1.yaml`. The checked-in file is
JSON-compatible YAML so it works without a YAML dependency. Set the provider's
actual DeepSeek V4 Flash non-reasoning model name, one uniform temperature,
`top_p`, and output-token limit. The model name is deliberately not hardcoded
in Python.

Set the API key only through the configured environment variable:

```powershell
$env:DEEPSEEK_API_KEY = "..."
```

If the API does not return `completion_tokens`, configure the exact matching
tokenizer in `model.tokenizer_name` and install `transformers`. The runner will
not use character counts, word counts, or division-based estimates. A missing
reliable API count and unavailable matching tokenizer is an infrastructure
error, not a claimed token match.

General Guidance length control accepts only the API's actual
`completion_tokens` (or deterministic mock usage in tests), never a tokenizer
fallback. The formal Pilot uses one 10% tolerance, defining an inclusive integer
interval around the Failure Frontier token count with `ceil` for the lower bound
and `floor` for the upper bound. There is no parallel 5% analysis.

The `blueprint_render_v1` policy uses a compact structured Blueprint followed by
bounded material rendering. Stage A makes at most two Blueprint calls: one
initial call and one deterministic repair. Each has a 2048-token output
capacity. The Blueprint controls what content may be discussed and must be
strict JSON with four arrays: 2-4 constraints, 1-2 approaches, 2-4 correctness
claims, and 3-6 implementation risks. It may contain neither code nor Markdown.
Blueprint completion tokens are audit data and never participate in FF/GG token
matching.

Stage B renders the validated Blueprint with a fixed 8192-token capacity. Stage
C permits at most two deterministic material revisions, also with 8192-token
capacity. Thus one episode makes at most two Blueprint calls, three material
calls, and five GG calls total. Capacity is not a length target and does not
widen the registered interval. Failure Frontier and Success Teaching material
calls retain their independent 16384-token limit.

Material rendering may use only content units in the Blueprint. It may not
discover, introduce, evaluate, or reject a new algorithmic direction, narrate
open-ended thought, or output code or pseudocode. Soft section budgets allocate
15% to constraints, 45% to approaches, 20% to correctness and edge cases, and
20% to implementation checks. Deterministic paragraph caps are two per section
through target 1600, three through 3500, and four above 3500, with at most four
sentences per paragraph.

A solver attempt uses the fixed `two_stage_v1` protocol: one bounded planning
call followed by one mandatory final-submission call. Teacher, Baseline, FF,
and GG solvers all receive a 2048-token planning limit and an 8192-token final
limit. Planning may compare at most two directions and must select one, but its
text is never submitted. Empty, structurally incomplete, or truncated planning
is preserved with a validation warning and still proceeds to the one final
call; it is never resampled.

The final call receives the role's original visible input and only that role's
own planning. The prompt requires exactly one syntax-complete Python source file
in exactly one `python` code fence, with no text outside the fence. Runtime
extraction is deliberately more tolerant: if exactly one Python fence is
present, surrounding text or non-Python material is ignored and only that
fence's source is eligible for at most one Judge submission. A complete fenced
response may still be submitted when its API finish reason is `length`, while
the truncation remains recorded; a missing or unclosed Python fence, multiple
Python fences, or invalid source is a final-output validation failure and
receives no rescue call.

All Blueprint attempts and material versions are preserved with prompt hashes,
source versions, budgets, operation and recovery modes, usage, finish reason,
semantic findings, and interval/target distance. The preferred material
structure contains `## Constraint Analysis`, `## Algorithmic Directions`,
`## Correctness and Edge Cases`, and `## Implementation Checks`; exact heading
conformance is audit-only. `semantic_completeness_v2` still determines whether
constraints, approaches, correctness, and implementation are substantive.

Material candidates use the states `MATCHED`, `COMPLETE_TOO_LONG`, `TOO_SHORT`,
`INVALID_CONTENT`, `TRUNCATED_TOO_LONG`, and `FORBIDDEN_CONTENT`. The first
normally finished, semantically complete, non-forbidden response in the interval
is accepted immediately. A truncated response is never a match, revision source,
fallback, exploratory candidate, or Student material.

When a complete overlong candidate exists, revision compresses the closest such
anchor using deletion, merging, and abbreviation only. The initial retain ratio
is `clamp(target/source, 0.50, 0.98)`. A later compression uses observed token
feedback and keeps the same complete long anchor; missing semantic categories
produce deterministic validator feedback, including concrete implementation
coverage. With no long anchor, a complete short result is rerendered from the
Blueprint using scaled section budgets. A truncated result is never copied: the
next call rerenders the same Blueprint under a dedicated bounded recovery prompt.
Requests record their signatures, and duplicate regeneration is replaced by a
deterministic recovery form.

If no strict candidate exists after three material calls, fallback selection is
limited to `finish_reason=stop`, semantically complete, non-forbidden material.
It sorts by distance to the registered interval, then distance to the FF target,
then prefers a candidate at or above the target, then the earlier version. This
fallback adds no model call, never satisfies token matching, and is eligible only
for explicitly exploratory analysis. If no safe fallback exists, no material is
selected, GG generation fails, and no invalid or truncated text is given to the
GG Student. A successful API response that fails content validation is recorded
as `gg_content_validation`, not as a network/API error.

Resume reuses completed Blueprints and material candidates without another model
call. Pre-Blueprint artifacts remain readable as legacy evidence, are explicitly
marked incompatible with the new policy, and are never retroactively assigned a
Blueprint or automatically resampled.
`match.json`, the per-problem teaching-material record, and the run summary
separately record `matched_within_tolerance`, `fallback_outside_tolerance`, and
`unmatched_no_fallback`; fallback output is never reported as a ±10% match.
Execution validity and treatment-comparison eligibility are separate concepts.
`valid_episode` records whether the episode and its artifacts are valid at the
infrastructure level. `condition_comparison_eligible` is exclusively the gate
for the preregistered strict Baseline / FF / GG treatment comparison.

The canonical `teacher_failure_strict_v2` policy is derived once from finalized
episode state immediately before `record.json` is written. A strict comparison
requires a Teacher-failure branch, a valid episode, a normally finished and
semantically valid GG within the registered token interval, no fallback, all
three required Student stages completed, valid Student materials, and no
infrastructure error. The record also stores deterministic reason codes.

Teacher-success episodes are never treatment-comparison eligible, even when
the Teacher and all Students are AC, because all three Student slots receive
the same Success Teaching Material. They remain useful for execution-chain and
success-material observations. A complete and semantically valid GG fallback
may be marked separately as `exploratory_comparison_eligible`, but fallback
never satisfies strict token-matched eligibility. Truncated, semantically
incomplete, or forbidden fallback material is not exploratory eligible.

Summaries rederive the policy defensively instead of trusting a legacy boolean.
For historical artifacts they preserve the runner-reported value, derive a
separate protocol value, and emit compatibility warnings without modifying the
source record. `tools/analyze_pilot_eligibility.py --run-dir <historical-run>`
provides the same read-only analysis without exposing model or Judge content.

GG token-matching tolerance was changed from 5% to 10% before the first formal
Pilot and remains unchanged by `blueprint_render_v1`. GG validity requires
substantive coverage of all four semantic categories; exact four-section heading
conformance is an independent audit signal. Historical formal and smoke
artifacts retain the policy and prompts that actually produced them; the new
policy applies only to future runs.

The historical `smoke-3980-fenced-20260717T173113` artifacts remain unchanged.
That run remains useful for infrastructure, two-stage solver, and fenced-final
extraction validation, but not for condition comparison. Its observed GG
headroom and token-match failures motivated later controller updates; current
capacity policy applies only to future runs.

For a clean Git worktree, set `execution.output_root` to a directory outside
the repository. Run directories may contain full model prompts and responses
and must be treated as internal research artifacts.

## Commands

Preview all roles and rendered prompts without API or judge access:

```powershell
python -m experiments.run_pilot --config experiments/configs/pilot_v1.yaml --mode dry-run
```

Exercise the full state machine with deterministic mock responses and the
frozen Docker judge:

```powershell
python -m experiments.run_pilot --config experiments/configs/pilot_v1.yaml --mode mock
```

An optional scripted mock JSON can be supplied with `--mock-responses`. Live
execution is:

```powershell
python -m experiments.run_pilot --config experiments/configs/pilot_v1.yaml
```

Use `--output-root <directory>` to place artifacts outside the repository
without changing the checked-in configuration.

Reusing the same `--run-id` resumes planning, final generation, and submission
independently. A model response already persisted successfully is never sampled
again. `JUDGE_ERROR`, Docker failure, network failure, and rate limiting are
infrastructure outcomes; judge retry reuses the identical final submission and
does not create another model attempt.

## Architecture and isolation

- `config.py` validates the single-model, non-reasoning policy and rejects
  literal API keys.
- `model_client.py` provides live OpenAI-compatible and deterministic mock
  clients. Only network/infrastructure errors are retried.
- `prompts.py` builds every role's problem view from `problem.json` and public
  tests only.
- `code_extraction.py` extracts the unique syntax-complete fenced Python block
  from the final stage, tolerates surrounding response text, and never repairs,
  combines, or supplements output from planning.
- `orchestrator.py` owns branching, coarse verdict mapping, token matching,
  state files, artifact paths, resume, and summaries.
- `DockerJudge` remains the only submission evaluator. A model receives only
  its system/user prompt; it has no filesystem access. Untrusted submissions
  are mounted with only their source and the current input, so they cannot read
  sibling Student artifacts.

The model-visible verdict is only `AC`, `WA`, `CE`, `RE`, `TLE`, or `MLE`.
`JUDGE_ERROR` invalidates the episode. Hidden inputs, expected/actual output,
case position, pass counts, stderr, stack traces, oracle data, checker details,
and sandbox logs remain internal.

## Run artifacts

Each run contains a redacted config snapshot, run state, per-problem Teacher,
teaching-material, and Student directories, separate `planning/` and `final/`
model-call records and stage metadata, extracted final submissions, internal
judge records, `results.jsonl`, `summary.json`, and `summary.md`. Each model-call
record preserves prompts, raw response, token usage source, finish reason,
truncation flag, request ID, model parameters, latency, and hashes. No API key
or environment dump is written.

The summary reports Teacher and Student AC counts, breakthroughs on Teacher
failures, the two directional FF/GG signal lists, token-match measurements,
truncations, and invalid infrastructure episodes. With five single samples it
is explicitly a chain-validation pilot and makes no statistical-significance
claim.

## Tests

```powershell
python -m unittest discover -s experiments/pilot_tests -v
python -m unittest discover -s tests -v
```

Pilot tests live outside frozen `tests/`; adding a file to that closed scope
would correctly invalidate the baseline manifest.
