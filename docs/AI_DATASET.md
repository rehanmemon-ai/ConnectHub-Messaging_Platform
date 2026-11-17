# Synthetic AI evaluation datasets

## Retrieval dataset v1

`backend/evals/dataset.py` deterministically builds 120 synthetic messages across 12 engineering topics and 60 queries: exact terms, paraphrases, questions, ambiguous wording, and 12 negative queries. Each positive query has graded relevance judgments from 1–3. Fixtures deliberately include newer keyword distractors and older relevant messages. No fixture is copied from a user, customer, college, or private ConnectHub room.

Message schema: `id`, synthetic `room`, `text`, `topic`, and stable `sequence`. Query schema: `id`, `text`, `category`, and `{message_id: grade}` relevance. Binary metrics treat every grade above zero as relevant; nDCG uses the full grade.

## Summary dataset v1

`backend/evals/summary_dataset.py` contains 18 two-party synthetic transcripts with required facts, forbidden unsupported claims, reference summaries, conflicts/unresolved states, and a prompt-injection case. Reference summaries are review aids, not claims of a single perfect wording.

## Review and versioning

Dataset versions are constants in the fixture modules. Change a version whenever messages, queries, judgments, or rubric meaning changes. Review changes for accidental personal data, ambiguous relevance, leakage from query wording, and unrealistic topic balance. Never replace these fixtures with production exports.
