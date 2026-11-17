# ConnectHub QA results

Execution date: 2026-11-17. Revision under review: local changes based on `04877d0f972fc85a096be989c9f1cd56fafb96c8` on `main`. No commit, push, deployment, production setting change, or production database mutation was performed.

## Final automated evidence

| Gate | Result |
|---|---|
| Backend Pytest | **PASS — 97 passed, 0 failed, 0 skipped**; one upstream Starlette/httpx deprecation warning |
| Ruff lint / format | **PASS**; 82 Python files formatted consistently |
| Python dependency consistency | **PASS** — `pip check` found no broken requirements |
| Alembic | **PASS** — history reaches `20261117_0003`; `alembic check` reports no new upgrade operations |
| Frontend ESLint / TypeScript | **PASS** |
| Frontend Vitest | **PASS — 21 passed** |
| Vite production build | **PASS** |
| Playwright | **PASS — 3/3** authenticated scenarios against guarded local PostgreSQL test data |
| npm audit | **PRODUCTION PASS — 0 production vulnerabilities.** Full audit currently reports 12 high development-tooling findings; its only listed fixes are incompatible major downgrades, so the tested Vite 8/Vitest 5 toolchain remains unchanged. |
| Offline retrieval evaluation | **PASS / BASELINE ONLY** — 120 messages, 60 queries, K=5; P=.106667, recall=.177778, MRR=.483333, nDCG=.117554, MAP=.177778 |
| Live Gemini evaluation | **NOT RUN** — no approved key in the process; no live claim is inferred from fakes |

The first Playwright continuation run failed because the new password visibility buttons made broad label locators ambiguous. Role-specific input locators corrected the test harness; the product controls remained accessible. An older Vitest registration test required the same selector maintenance. Final results above are after those corrections.

## Corrected defects

- Chat follows new messages only when the reader is near the bottom; loading older history preserves position and a jump-to-latest control appears when appropriate.
- Chat height now follows the visual viewport and mobile safe area so the composer remains reachable.
- Login and registration password fields now have independent, accessible show/hide controls.
- Connection and read-receipt presentation has stronger contrast; a real favicon and product metadata are present locally.
- WebSocket disconnect awaits cancelled writer/typing tasks, avoids swallowing unexpected exceptions, and prevents stale typing-task cleanup from removing a replacement task.
- Live Gemini evaluators now write strings rather than accidental one-element tuples and report average precision/MAP-compatible data. Fake-provider tests verify valid JSON, expected keys, both output paths, and write failures.

## Browser and deployment evidence

Isolated E2E verified real registration/session restoration, public and private room workflows, independent users, live messages, idempotent retry, exact search, AI-disabled behavior, critical/serious axe results, responsive navigation, viewport safety, and bounded authenticated HTTP responsiveness.

Read-only public smoke checks returned HTTP 200 for the backend readiness endpoint, frontend root, and frontend-proxied readiness endpoint. The deployed `/favicon.svg` currently returns the SPA HTML fallback, so the new favicon is **LOCAL VERIFIED / NOT DEPLOYED**.

## Limitations

- Production AI remains disabled. Real Gemini embedding retrieval and summary quality are **NOT RUN**.
- Synthetic offline exact matching is a deterministic baseline, not semantic Gemini performance.
- The browser suite does not claim exhaustive manual verification of every rare failure state or every notification mutation; backend/frontend automated coverage supplies the additional evidence recorded in the feature matrix.
- Playwright video recording was attempted but its bundled FFmpeg executable was unavailable. No encoder was downloaded, so no WebM, MP4, or 8–12 minute rendered walkthrough was created; the case study contains the storyboard and narration/edit outline.
