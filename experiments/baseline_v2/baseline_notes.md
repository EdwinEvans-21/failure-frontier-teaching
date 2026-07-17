# Benchmark Baseline v2 Notes

`failure-frontier-baseline-v2` is the first benchmark baseline whose five
canonical `problem.json` files have been audited as self-contained model-visible
specifications.

The historical `failure-frontier-baseline-v1` tag and manifest are retained
unchanged. Baseline v1 contains a specification defect: at least the binary
transformation problem omitted the meanings and directions of its two allowed
operations from the runtime `problem.json`. It must not be used for behavioral
experiments or condition comparisons. Runs made from it may still be useful for
infrastructure validation when separately marked as such.

README files are human documentation only. They are neither runtime sources of
problem facts nor members of the baseline v2 frozen-file set. The v2 manifest
uses an explicit semantic allowlist and rejects any frozen path whose basename,
case-insensitively, is `README.md`.

