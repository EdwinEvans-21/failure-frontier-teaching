# Failure-Frontier Teaching Pilot v1

This module runs the minimal five-problem pilot above the frozen
`failure-frontier-baseline-v1` judge. It does not change problem statements,
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

Reusing the same `--run-id` resumes completed stages. A model response already
persisted successfully is never sampled again. `JUDGE_ERROR`, Docker failure,
network failure, and rate limiting are infrastructure outcomes; judge retry
reuses the identical submission and does not create another model attempt.

## Architecture and isolation

- `config.py` validates the single-model, non-reasoning policy and rejects
  literal API keys.
- `model_client.py` provides live OpenAI-compatible and deterministic mock
  clients. Only network/infrastructure errors are retried.
- `prompts.py` builds every role's problem view from `problem.json` and public
  tests only.
- `code_extraction.py` accepts exactly one complete Python fenced block and
  never repairs output.
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
teaching-material, and Student directories, model-call records, extracted
submissions, internal judge records, `results.jsonl`, `summary.json`, and
`summary.md`. Each model-call record preserves prompts, raw response, token
usage source, finish reason, truncation flag, request ID, model parameters,
latency, and hashes. No API key or environment dump is written.

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
