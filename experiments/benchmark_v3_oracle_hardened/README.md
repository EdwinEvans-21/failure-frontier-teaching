# benchmark_v3_oracle_hardened

This versioned benchmark augments, but does not replace, the historical benchmark. It hardens the 16 problems represented in the lineage analysis with deterministic small exact-oracle tests, named adversarial families, and a separate resource stress layer. The remaining 15 expanded problems are explicitly `NOT_HARDENED_IN_V3`.

`judge_v3_oracle_hardened` extends the existing Docker trust boundary with a batch worker. The container receives submission bytes, entrypoint metadata, and inputs only. Expected values remain on the trusted host and exact comparison reuses `ffjudge.runner.equivalent`. Every call is timed independently inside the already-started container. Network is disabled, the filesystem is read-only, capabilities are dropped, and containers are removed in `finally`.

File hashes use raw bytes. Stable replay artifact hashes use canonical UTF-8 JSON with sorted keys and exclude measured runtime, which is deliberately nondeterministic. Runtime remains recorded separately. A counterexample proves a program wrong; passing finite tests is reported only as `NO_COUNTEREXAMPLE_FOUND`, never as formal verification.

The replay is observational. It never calls a model and never fills descendants that were not generated because an old false AC stopped a lineage.
