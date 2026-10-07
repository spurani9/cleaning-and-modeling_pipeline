# CloudNova FDE — AI Development Instructions

## Mission
Build the smallest production-shaped Track B solution that is driven by the written specs. Do not invent business rules that are not documented; surface ambiguity explicitly.

## Source of truth
1. `data/BUSINESS_CONTEXT.md` — customer/business rules.
2. `specs/data_contract.md` — cleaned schema and deterministic transformations.
3. `specs/query_contract.md` — natural-language query contract and safety constraints.
4. `specs/eval_spec.md` — acceptance criteria.

## Engineering rules
- Prefer deterministic transformations for financial/business logic; the LLM must not calculate revenue or MRR.
- Keep raw data immutable and write cleaned data to a separate artifact.
- Never silently discard conflicting duplicate invoice records. Apply the documented deterministic policy and retain an audit reason.
- Use explicit schemas, validation, typed functions, parameterized SQL, and structured logging where practical.
- Query generation must be constrained to SELECT-only SQL over the governed view.
- Do not interpolate user text directly into SQL.
- Do not introduce cloud infrastructure unless it materially improves the 60-minute submission.
- Keep the system runnable locally with one command after setup.
- Every behavior added to code should have a test or eval case.

## AI workflow
Before implementing a feature:
1. Read the relevant spec.
2. State assumptions and ambiguities.
3. Implement the smallest change satisfying the spec.
4. Run tests/evals.
5. Review generated code for business-rule violations.

## Required review questions
- Could this double-count revenue?
- Could this misinterpret an ambiguous date?
- Could this execute arbitrary SQL?
- Could this silently change the customer's data?
- Is the behavior reproducible from a clean checkout?
