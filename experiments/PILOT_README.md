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
and `floor` for the upper bound. There is no parallel 5% analysis. GG output
capacity is intentionally larger than the accepted interval so the model can
finish naturally. Every initial, compression, expansion, and fresh-regeneration
GG call uses the same fixed capacity:

```text
gg_max_output_tokens = 8192
```

The API capacity no longer tracks the target or accepted upper bound. This does
not widen the accepted interval: a complete response above the 10% upper bound
remains too long, and every `finish_reason=length` response remains invalid.
Failure Frontier and Success Teaching material calls retain their independent
16384-token limit. GG's fixed limit is independent of both solver-stage limits.

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

All GG versions are preserved with their prompts, content, usage, finish
reason, required-section status, semantic coverage, validation findings,
interval distance, and target distance. Valid GG output must contain exactly
`## Constraint Analysis`, `## Algorithmic Directions`,
`## Correctness and Edge Cases`, and `## Implementation Checks`, once each and
in that order. Every section must contain substantive, complete coverage, with
no complete solution code or forbidden information. The first semantically
complete `finish_reason=stop`
response inside the interval is accepted immediately. A `finish_reason=length`
response is always invalid and can never become a complete candidate, rewrite
anchor, or final audit selection. The controller retains the closest complete
overlong and complete short candidates. Once a complete overlong candidate
exists, all later adjustments compress from that high-information anchor rather
than expanding a short response. If such a compression overshoots short, a
deterministic linear correction adjusts the requested retain ratio while still
using the same long source. Compression is editing-only: it may delete, merge,
abbreviate, condense, or minimally reorder existing material, but may not add
new content. If a first compression is invalid, the next compression receives
its missing-section feedback. Its retain ratio is deterministically corrected
from the prior requested ratio and observed token length; missing sections
receive an explicit approximate 20% allocation instruction. Expansion is
allowed only when no complete overlong candidate has ever been observed. If all
configured attempts fail, the closest
semantically complete normally-finished version is selected only for audit
display; this does not satisfy token matching, and the episode is excluded from
formal condition comparison. A successful API response that fails content
validation is recorded as `gg_content_validation`, not as a network/API error.
The top-level `condition_comparison_eligible` flag is derived at finalization:
an episode is eligible only when it is valid and has no infrastructure error,
protocol-output failure, or GG token-match failure. It is not maintained as an
independent mutable status flag.

GG token-matching tolerance was changed from 5% to 10% before the formal Pilot
and before the runner was frozen. Repeated smoke tests showed that bounded
rewrites under a 5% tolerance could destabilize the structure of otherwise
relevant guidance. GG validity now requires both the exact four-section protocol
and substantive semantic coverage within every section. The formal Pilot has
not yet run, and this change precedes the final runner freeze.

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
