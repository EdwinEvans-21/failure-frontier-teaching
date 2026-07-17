# Benchmark Baseline v3 Notes

`failure-frontier-baseline-v3` freezes the same five problem specifications,
formal tests, trusted oracles, formal generators, and Judge semantics as v2,
plus the corrected execution-time boundary: submission time is measured only
inside the running container, while a host-side Docker watchdog failure is an
infrastructure `INTERNAL_ERROR`, never a model `TIME_LIMIT_EXCEEDED`.

The baseline uses an explicit problem-and-Judge allowlist. Every file whose
basename case-insensitively equals `README.md` is excluded. Research prompts,
Pilot orchestration, run artifacts, logs, accepted examples, and intentionally
wrong submissions are also outside the v3 frozen scope.
