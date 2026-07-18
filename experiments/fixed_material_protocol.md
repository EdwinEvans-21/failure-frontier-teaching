# Fixed-Material Repeated Student Experiment v1

This experiment freezes the seven strictly eligible Teacher-failure episodes from
`expanded-exploratory-v1-20260718T044702Z`. It never regenerates Teacher, Failure
Frontier, or General Guidance material.

For each problem, each of `baseline`, `naive_ff`, `critical_ff`, and
`general_guidance` receives ten independent Student samples. Every sample has one
Planning call, one Final call, and at most one Judge submission. Model-output
failures are observations and are never resampled. Only infrastructure failures may
be resumed in the same registered sample cell and Run ID.

The primary estimand is the problem-macro-averaged AC-rate difference between
Critical FF and Naive FF. The seven problems are the paired analysis units; the 280
cells must not be treated as 280 independent problem draws.

The source snapshot, schedule, prompts, configuration, Git identity, and hashes are
written before the first API request. The source snapshot and historical run are
read-only. Baseline v3 and the expanded baseline must pass before execution.
