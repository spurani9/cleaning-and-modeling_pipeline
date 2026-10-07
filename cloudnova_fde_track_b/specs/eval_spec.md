# Evaluation Specification

The eval suite covers the six stakeholder questions in `BUSINESS_CONTEXT.md`.

Acceptance criteria:
- deterministic pipeline output is reproducible;
- normalized statuses/plans/cycles are valid;
- invoice_id is unique after deduplication;
- revenue uses only paid/refunded rows according to the business rule;
- MRR uses plan price × seats × discount and does not double-count annual invoice amounts;
- natural-language queries produce safe SELECT SQL;
- at least one known limitation is represented as an expected failure/ambiguity.

The conflicting-invoice deduplication policy is explicitly treated as an exercise assumption and surfaced in the README.
