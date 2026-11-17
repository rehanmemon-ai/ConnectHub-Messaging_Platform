# ConnectHub project freeze

Status date: 2026-11-17. The implemented product scope is frozen after the AI-evaluation milestone, subject to successful final regression.

## Complete intended scope

Database/session foundation; registration/login/logout/profile; public/private rooms; invitations and membership controls; persistent idempotent messages; history/search; authenticated WebSockets; typing/presence/read receipts; notifications; responsive React client; optional summaries and semantic search; synthetic evaluation; security, operations, deployment, backup, and portfolio documentation.

## Accepted limitations

- One backend process owns real-time connections; no distributed presence or broadcast.
- JSONB cosine ranking uses a newest-first candidate window, not a global vector index.
- Gemini is an optional external dependency; AI is disabled by default and live quality/quota is unverified.
- Controlled staging still needs owner/provider/budget/privacy approval. Public production and isolated restore rehearsal are not complete.
- No custom ML model is trained and summaries are not retrieval-grounded RAG.

## Allowed maintenance

Security vulnerabilities, critical/high reliability defects, dependency or provider deprecations, data-integrity problems, and production incidents may justify focused changes with regression evidence. Embedding-model changes require a new profile, evaluation, explicit re-embedding plan, and controlled cutover.

## Not planned

Random feature expansion, cosmetic rewrites, microservices, Kafka/Redis/pgvector without measured need, multi-worker deployment without shared coordination, or infrastructure migration for portfolio appearance. New product scope requires a separately approved objective and acceptance criteria.
