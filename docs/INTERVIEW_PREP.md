# ConnectHub interview preparation

## Pitches

**30 seconds.** ConnectHub is a full-stack real-time messaging system I can explain end to end: opaque sessions, PostgreSQL transaction locks, persistent WebSockets, private-room authorization, and optional Gemini summaries and semantic search. Its AI work is versioned, privacy-gated, recoverable, and evaluated on labelled synthetic data rather than presented as an API-call demo.

**90 seconds.** The React client uses REST for durable state and one authenticated WebSocket for events. FastAPI validates a database-backed session and room membership; PostgreSQL commits each message before the process-local manager broadcasts it. Private rooms use transactional invitations and concealment. AI is disabled by default. Approved messages become profiled durable jobs, document and query task types stay compatible, and cosine scoring happens inside a disclosed recent-candidate window. A 120-message/60-query benchmark measures a literal baseline; live Gemini quality remains explicitly unrun. The main trade-offs are one backend process and JSONB vectors rather than distributed pub/sub or pgvector.

**Three minutes.** Start with the system diagram, then trace login, CSRF mutation, membership-row lock, idempotent message commit, WebSocket broadcast, reconnect/reconciliation, and durable notification. Explain that external AI is a separate trust boundary: no automatic disabled backlog, owner-controlled backfill, versioned profiles, bounded retries, finite-vector validation, and versioned summary cache. Describe P@K, recall, MRR, nDCG, the measured exact-search baseline, and why real semantic quality is not claimed without a live synthetic-only run. Close with release status: locally verified, controlled staging conditional, public production not run.

## Architecture reasoning

- REST owns recoverable snapshots and mutations; WebSockets carry low-latency changes and reconcile from REST after reconnect.
- PostgreSQL is the source of truth for sessions, authorization, messages, receipts, invitations, notifications, jobs, vectors, and summaries.
- Opaque tokens enable server-side revocation; stored digests reduce damage from a session-table leak. CSRF protects cookie-authenticated writes.
- Membership locks serialize message send/removal and owner transitions. Commit-before-broadcast prevents phantom events.
- The connection manager is process-local, so deployment deliberately uses one worker. Multi-worker operation needs shared pub/sub, presence, and rate limiting.

## AI engineering explanations

- An embedding maps text to a numeric vector whose geometric proximity can approximate semantic relatedness.
- Corpus text and search queries have different retrieval roles; Gemini's document/query task types optimize the shared space for that asymmetry.
- Cosine similarity divides the dot product by both magnitudes. It compares direction, but invalid, non-finite, zero, or incompatible vectors must be rejected.
- Candidate generation determines recall before ranking. ConnectHub's newest-first limit can exclude an old perfect result; JSONB is simple but not a scalable ANN index.
- Precision@K asks how clean the first K are; Recall@K asks how much relevant material was found; MRR rewards an early first hit; nDCG rewards correct graded ordering.
- Labels matter because no metric can tell relevance from API success alone. The exact-substring baseline makes the semantic experiment comparative.
- Summary caching keys source range, provider, model, and prompt version. Bounded characters/messages prevent runaway context and metadata discloses truncation.
- Durable jobs isolate message persistence from outages. `SKIP LOCKED`, attempts, backoff, terminal failure, and stale recovery make behavior inspectable.
- This is an AI-powered application, not model training and not full RAG: semantic results are not supplied as grounding to the summary generator.

## Question bank with answer direction

### Python/backend

1. **Why async?** Network/database waits can interleave; CPU cosine work still blocks and must remain bounded.
2. **Where do exceptions cross the API boundary?** Domain/provider errors become stable safe envelopes; secrets and raw provider bodies are not returned.
3. **Why dependency injection?** Settings, sessions, and auth context are replaceable/testable at route boundaries.

### SQL/PostgreSQL

1. **Why row locks?** They serialize authorization-sensitive state changes across connections, unlike an in-process mutex.
2. **What does `SKIP LOCKED` do?** Concurrent workers claim different eligible jobs without waiting, while state remains durable.
3. **At-most versus at-least one owner?** A partial unique index enforces at most one; transactional room creation/mutation enforces the minimum.

### Security/authentication

1. **Why not JWT?** Immediate revocation and WebSocket session checks outweigh stateless-read benefits at this scale.
2. **Why CSRF with HttpOnly cookies?** Browsers attach cookies automatically; a session-bound header/cookie proof plus Origin validation distinguishes intended writes.
3. **How are private rooms concealed?** Unauthorized direct access returns 404 rather than confirming existence.

### REST/WebSockets and system design

1. **Why commit first?** Broadcasting before commit can show data that later rolls back.
2. **How are reconnect duplicates avoided?** Client UUID idempotency plus server replay and client ID deduplication.
3. **How would you scale?** Add shared broadcast/presence/rate-limit state and then permit multiple workers; prove ordering and failure semantics first.

### Retrieval/LLMs/evaluation

1. **Why not call API success “quality”?** Quality requires labelled relevance/factuality evidence; transport tests only prove integration.
2. **Why profile vectors?** Model, dimension, or task-space changes can make cosine scores meaningless; profile matching quarantines incompatibility.
3. **Why no automatic embedding-2 upgrade?** Its space is incompatible, so the corpus needs evaluated re-embedding and controlled cutover.
4. **What biases the benchmark?** Synthetic topic balance, judgement subjectivity, small corpus, and query wording; version and review labels.
5. **How do you evaluate summaries?** Fact coverage, unsupported claims, omissions, readability, contradiction handling, and injection resistance, with human review.

### Reliability/DevOps

1. **What survives provider outage?** Messages; jobs retry independently and eventually enter a visible failed state.
2. **What is staging-ready versus production-ready?** Local evidence supports a controlled pilot; hosting/TLS/secrets/monitoring/restore evidence blocks public production.
3. **What would you monitor?** Health, DB saturation, WebSocket counts/queue drops, job age/failure, provider duration/retry/usage, and error rates—never message bodies.

## Honest limitations

Candidate-limited JSONB ranking may miss older relevant messages; one process limits availability/scale; live Gemini quality/quota/cost is unverified; public deployment and isolated restore rehearsal are not complete; provider privacy approval is pending. Do not claim users, traffic, production availability, custom model training, or RAG.

## Hands-on comprehension exercises

1. Change a message validation bound and add the failing/passing tests.
2. Trace the exact membership lock shared by send and removal.
3. Inspect the two Gemini payload task types and explain profile compatibility.
4. Compute cosine similarity for `[1,0]` and `[1,1]` by hand.
5. Run one benchmark query and explain every judged message and metric.
6. Force an embedding exception and inspect its durable retry/failed transition.
7. Reproduce a private-room cross-user denial.
8. Add a regression for candidate-window accounting without changing production data.

## Portfolio positioning

- **AI/GenAI:** provider integration, embeddings, evaluation, privacy, cost/latency evidence, and failure handling.
- **Backend/software:** async APIs, PostgreSQL consistency, secure sessions, WebSockets, and operations.
- **Full stack:** typed React workflows connected to real contracts and multi-user E2E.

Truthful resume bullets:

- Built and tested a FastAPI/PostgreSQL/React messaging platform with database-backed sessions, transactional room authorization, and authenticated WebSockets.
- Designed privacy-gated Gemini summary and semantic-search pipelines with compatible query/document embeddings, durable retries, and versioned caches/profiles.
- Created a 120-message, 60-query synthetic retrieval benchmark with P@K, Recall@K, MRR, nDCG, and an exact-search baseline; kept unrun live-model quality clearly separated.
