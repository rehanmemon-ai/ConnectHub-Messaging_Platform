# AI evaluation and model evidence

Status date: **2026-11-17**. AI provider calls were **NOT RUN** in this milestone. `AI_ENABLED=false` was preserved.

## Retrieval method

ConnectHub stores `RETRIEVAL_DOCUMENT` vectors and creates `RETRIEVAL_QUERY` vectors under one profile: provider, model, dimensions, and profile version. Only an exact profile match is eligible. The production ranker selects at most the newest configured number of indexed room messages and computes exact cosine similarity inside that window. Therefore it is recency-bounded subset ranking, not global vector search.

The deterministic benchmark provides Precision@K (share of K results that are relevant), Recall@K (share of all judged-relevant items found), MRR@K (reciprocal rank of the first relevant result), nDCG@K (graded relevance with rank discount), and MAP@K (mean precision over relevant hits). Unit tests cover perfect, poor, empty, and no-relevance cases.

## Measured offline exact-substring baseline

Command, from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m evals.run_retrieval --k 5 --output evals\exact_baseline_full.json
..\.venv\Scripts\python.exe -m evals.run_retrieval --k 5 --candidate-limit 50 --output evals\exact_baseline_candidate50.json
```

| System | Queries | P@5 | Recall@5 | MRR@5 | nDCG@5 | MAP@5 |
|---|---:|---:|---:|---:|---:|---:|
| Literal case-insensitive substring, all 120 messages | 60 | 0.1067 | 0.1778 | 0.4833 | 0.1176 | 0.1778 |
| Same baseline, newest 50 candidates | 60 | 0.0533 | 0.0889 | 0.2333 | 0.0583 | 0.0889 |

These are synthetic baseline measurements, not Gemini scores and not production accuracy. The candidate-50 result demonstrates the expected recall loss when older relevant messages fall outside a recency window. Timing in the JSON is local in-memory baseline timing, not API or database latency.

## Semantic and summary quality status

Real `gemini-embedding-001` retrieval metrics: **NOT RUN**. Real `gemini-3.5-flash-lite` summary quality: **NOT RUN**. No credential was read or requested, no live call was made, and no score is inferred from test doubles. An authorized future run must use only the synthetic fixtures, record model/profile/dimensions/candidate limit, preserve raw ranked IDs without secrets, and capture the date and provider account tier.

After the owner approves provider terms/cost and supplies `AI_API_KEY` through a proper process secret mechanism (never chat, source, command history, or committed files), set process-scoped `AI_ENABLED=true` and run from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m evals.run_live_gemini --confirm-synthetic-only `
  --retrieval-output evals\live_retrieval_review.json `
  --summary-output evals\live_summary_review.json
```

The runner reads only source-controlled synthetic fixtures and does not connect to either application database. It refuses a missing/disabled provider configuration. Generated live outputs require review before publication; summary `human_scores` intentionally remain null until a person applies the rubric.

The 2026-11-17 closeout corrected both live output writers to serialize text strings rather than accidental one-element tuples. Fake-provider regression tests now verify valid JSON, expected retrieval/summary keys, both output paths, average precision reporting, safe omission of credentials, and propagated write failures. These tests validate the evaluator boundary; they are not evidence of a live Gemini response.

For each of the 18 summary fixtures, a human reviewer scores factual consistency, required-fact coverage, unsupported claims, significant omissions, readability (1–5), and prompt-injection resistance. Deterministic checks can flag missing expected phrases or forbidden claims, but human review remains necessary; an LLM judge is supplementary, not ground truth.

## Operational telemetry

Provider logs record operation, provider, model, monotonic duration, retry count, safe outcome category, and provider `usageMetadata` when returned. They do not log prompts, message text, keys, cookies, room names, or vectors. Embedding profile/task and durable job attempts are stored or inferable from profiled job state. Cache hit/miss is represented by the summary response and stored summary metadata. Exact cost is **UNMEASURED**: calculate it later from provider-reported usage and a dated [official pricing table](https://ai.google.dev/gemini-api/docs/pricing), recording unavailable fields rather than inventing them.

## Model lifecycle review

Official documentation checked 2026-11-17: [embedding task types](https://ai.google.dev/gemini-api/docs/embeddings), [models](https://ai.google.dev/gemini-api/docs/models), and [deprecations](https://ai.google.dev/gemini-api/docs/deprecations). The configured `gemini-embedding-001` has a documented 2028-05-14 shutdown date; `gemini-3.5-flash-lite` is listed as stable with no announced shutdown date. The source default and `.env.example` intentionally match the existing Render override. Gemini embedding-2 is an incompatible vector space, so adoption requires a new profile, explicit synthetic evaluation, bounded re-embedding, cutover, and later cleanup approval—never mixed vectors or a database reset.

## Failure analysis and next experiment

Known failures include paraphrases that literal search cannot match, keyword distractors, negative-query false positives, and old relevant content outside the candidate window. The next authorized experiment is a synthetic-only live embedding run comparing candidate limits 50, 100, and full corpus against the same judgments. A production pgvector migration is not justified until measured recall/latency thresholds demonstrate the need.
