# Provenance-Stratified Failure Frontier v2

This protocol is an explicit opt-in extension. It does not reinterpret or rewrite historical `naive_ff`, `failure_frontier`, or `critical_failure_frontier` artifacts. Legacy configurations continue to render the legacy prompt files. A v2 configuration must select every registered v2 policy and the conditions `baseline`, `direct_ff_v2`, `critical_ff_v2`, `flat_ff_v2`, and `general_guidance` explicitly.

## Source classes

`DIRECT_FACT` is restricted to registered raw records: the standardized submission-level final error type, exact submitted code, its SHA-256, and exact raw excerpts. A natural-language recognition, summary, complexity statement, semantic judgment, or causal statement is never a Direct Fact.

`EVIDENCE_GROUNDED_INFERENCE` is fallible FF-organizer analysis with a short reproducible chain to the public problem, public constraints, exact submitted code, or final error type. It is neither an objective fact nor a formal proof. Its support status is `PROVISIONALLY_SUPPORTED` or `PARTIALLY_SUPPORTED`.

`LOW_CONFIDENCE_HYPOTHESIS` contains every Teacher-generated natural-language artifact and any organizer explanation without a short visible evidence chain. Ambiguous classification fails closed to this class.

## Failure path

After a submission-level Teacher failure, the runner deterministically exposes only one standardized final error type. It makes one Teacher failure-analysis call and one shared FF-organizer call. `INTERNAL_ERROR` remains `JUDGE_ERROR`; it exits as an infrastructure failure before either call or any Student treatment.

The deterministic payload builder supplies the exact submitted code once as a Direct Fact source. It supplies complete, verbatim Teacher Planning, Final natural language, and Teacher failure analysis as separately hashed low-confidence sources. The compact FF Record holds only raw source references, organizer inferences, provenance-linked exact excerpts, and optional organizer hypotheses. It cannot reproduce the complete sources.

Direct FF and Critical FF receive byte-identical serialized payloads. Their request is represented by `shared_solver_prompt`, `condition_specific_instruction`, `shared_failure_payload`, and `shared_output_requirements`. Only `condition_specific_instruction` differs. Direct is neutral; Critical requests selective review of a small number of consequential claims. Both use the unchanged two-stage solver, Final static prompt, extraction, submission, model parameters, and token limits.

Flat FF is an additional presentation control. It is built deterministically from the same exact submitted code, standardized error type, three complete raw Teacher artifacts, source metadata, and every FF-organizer record field. It removes the three confidence-tier wrappers, notices, headings, and grouping; it does not summarize, add, omit, or regenerate the underlying information. Flat FF uses the byte-identical `direct_ff_v2.md` instruction and the same solver budgets and execution path as Direct FF. Thus Direct versus Flat isolates provenance-tier presentation, while Direct versus Critical isolates the condition instruction.

Baseline receives only the formatted public problem in its user prompt. General Guidance remains isolated from every Teacher artifact, verdict, FF Record, and shared payload. Under `semantic_complete_no_length_v2`, GG is accepted by semantic completeness, content safety, and a complete `finish_reason=stop` response; the historical ±10% FF token interval is neither model-visible nor an eligibility condition. The fixed 8192 output-capacity ceiling, validated blueprint, four semantic regions, no-code rule, and bounded semantic/truncation repair attempts remain in force. Legacy configurations retain `token_interval_v1`. On Teacher success, the existing single success material is still supplied identically to every configured Student. `AC` means the submission passed the current evaluator; it is not a formal proof, uniqueness claim, or global optimality guarantee.

## Persistence and compatibility

Each v2 failure stores raw source artifacts, hashes, the FF Record, the rendered stratified and flat payloads, policy versions, and both renderer versions. Existing model-call resume logic rejects prompt-hash or model-configuration drift and reuses completed calls. Rebuilding either payload is deterministic and locked by source, record, and payload hashes. Legacy artifacts lacking v2 fields remain legacy and are not upgraded.

The offline audit generator is `tools/generate_provenance_ff_v2_audit.py`. Its checked output is under `prompt_audits/provenance_stratified_ff_v2/`. The dry-run template is `experiments/configs/provenance_stratified_ff_v2.example.yaml`; its mode is `dry-run` and it accesses neither API nor Judge.
