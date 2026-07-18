You are analyzing the failure frontier of one competitive-programming attempt.

You may use only the following supplied evidence:

* the public problem statement;
* the solver's planning response;
* the solver's final response;
* the extracted submitted code;
* the coarse judge verdict.

The judge verdict is only a category. It does not reveal the failing test, expected output, actual output, hidden constraints, or exact root cause.

Your task is to produce a concise failure-frontier report for a new solver.

## Evidence discipline

Clearly distinguish among:

1. **Direct observations**: facts explicitly visible in the supplied planning, final response, code, or verdict.
2. **Supported inferences**: conclusions strongly suggested by the visible evidence.
3. **Uncertain hypotheses**: plausible explanations that cannot be confirmed without hidden-test information.

Use uncertainty language whenever the evidence is insufficient.

Do not:

* claim knowledge of hidden tests;
* invent failing inputs, outputs, traces, or Judge behavior;
* present a hypothesis as a confirmed cause;
* infer a precise root cause solely from a coarse verdict;
* assume that the planning response and submitted code use the same algorithm;
* treat an idea mentioned during planning as implemented unless it appears in the final code.

## Scope restrictions

Analyze only the attempt that was supplied.

Do not:

* solve the problem from scratch;
* perform open-ended algorithm search;
* introduce more than two unresolved algorithmic directions;
* write complete pseudocode;
* write complete corrected code;
* provide a full replacement solution;
* narrate your internal reasoning process;
* repeat the same point in multiple sections;
* restate the full problem statement;
* include motivational, conversational, or meta commentary.

You may mention a possible state representation, invariant, data structure, or complexity requirement only when it directly clarifies an exposed limitation or unresolved frontier.

## Length and structure constraints

Produce exactly the six sections listed below, in the same order.

For each section:

* use at most 3 bullet points;
* each bullet must contain at most 3 sentences;
* avoid nested bullets;
* prioritize the most consequential evidence;
* stop after completing the final section.

The entire report should be concise and should normally remain below 1,500 words.

## Required sections

### Attempted Approach

Describe the algorithm and implementation actually selected in the final response.

Separately mention planning-stage alternatives only when they materially differ from the submitted approach.

### What May Still Be Valid

Identify at most three ideas, observations, invariants, subroutines, or implementation choices that may remain useful.

Do not imply that the overall solution is correct.

### Failure Evidence

Report only visible evidence from the code, responses, and coarse verdict.

State explicitly what the verdict does and does not establish.

### Likely Failure Causes

Give at most three candidate causes.

For each cause:

* label it as either `Supported inference` or `Uncertain hypothesis`;
* cite the relevant visible feature of the planning, final response, or code;
* explain briefly why that feature could cause failure.

Do not claim certainty unless the failure follows directly from the visible code and public problem statement.

### Exposed Frontier

Identify the smallest unresolved technical questions that separate the current attempt from a reliable solution.

Focus on missing invariants, insufficient state, invalid reductions, unjustified greedy choices, unhandled interactions, or complexity risks.

Do not provide the completed solution.

### Next Directions

Give at most three concrete investigation directions for a new solver.

Each direction should describe what must be checked, derived, or modeled next.

Do not provide implementation-ready pseudocode or complete algorithm steps.

## Final consistency check

Before answering, verify that:

* every factual claim is grounded in the supplied public evidence;
* observations and hypotheses are explicitly separated;
* no hidden test has been invented;
* no complete corrected solution or code has been provided;
* no more than two new algorithmic directions were introduced;
* all six required sections are present;
* the response ends immediately after `Next Directions`.
