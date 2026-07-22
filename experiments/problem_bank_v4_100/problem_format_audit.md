# LC Problem Bank v4 — Phase A Format Audit

- All directories: 36
- `lc-*` directories: 31
- Non-`lc-*` directories ignored: 5
- Existing `lc-*` comparator: exact only
- Existing `lc-*` entrypoint: class_method only
- Existing generated layout: problem.json, accepted.py, public_tests.json, hidden_tests.json, stress_tests.json, benchmark_metadata.json, mutants.json, and three wrong fixtures.
- Existing trusted oracles: centralized independent reference/bruteforce functions in `src/ffjudge/oracles/expanded_*.py`.
- Existing deterministic generator: `tools/generate_expanded_benchmarks.py`, seed 20260718.
- Existing baselines: baseline_v1, baseline_v2, baseline_v3, baseline_v3_expanded.

All 31 existing lc directories have 2 public, 12 hidden, 3 stress, and 3 mutant records. They therefore require v4 supplemental coverage. Supplements are versioned outside the legacy directories so old baselines remain byte-identical.

The fixed list overlaps existing 1547, 2035, and 2188. Reserve 2421 is also already present. Replacements selected in order: 2334, 2338, 2360.

The requested calibration categories cannot all be found inside the legacy 31: there is no unordered/custom comparator or function entrypoint there. The excluded legacy `exact_monotone_paths` directory demonstrates the custom-checker call chain.
