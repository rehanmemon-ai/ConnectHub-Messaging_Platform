# ConnectHub QA test plan

Last updated: 2026-11-17. This plan separates source inspection, isolated local automation, and read-only public smoke checks. Destructive automation may run only against the positively identified local `connecthub_test` PostgreSQL database; Neon production is never a test target.

## Quality gates

| Area | Required evidence |
|---|---|
| Backend | Ruff lint/format, `pip check`, full Pytest suite, Alembic history/check |
| Frontend | ESLint, TypeScript, complete Vitest suite, production Vite build, npm audits |
| Browser integration | Three Playwright scenarios using independent contexts and the guarded `_test` database |
| Security | Authentication/CSRF/Origin/authorization tests, safe path-only secret scan, dependency audit |
| AI | Fake-provider unit/integration coverage, deterministic synthetic retrieval evaluation, live provider clearly separated |
| Deployment | Read-only frontend, backend readiness, and frontend-proxied readiness checks |

## Functional coverage

- **Identity and profile:** registration, validation, login/logout, session restoration, protected routes, CSRF, profile read/update, and cross-user isolation.
- **Rooms:** public creation/discovery/join, private invitations, membership and owner authorization, duplicate/invalid operations, leave/delete rules, and empty states.
- **Messaging:** durable create/history/search, cursor ordering, client idempotency, independent live clients, reconnect, typing, presence, read position/receipts, malformed input, and revoked access.
- **Notifications and search:** persisted read/read-all mutations, exact room-scoped search, permission filtering, pagination boundaries, and disabled semantic-search status.
- **AI:** summary cache/version metadata, document/query task separation, durable embedding jobs, retry/failure states, profile isolation, candidate-bounded cosine ranking, and safe disabled behavior.
- **UX/accessibility:** password visibility, message-follow behavior, jump-to-latest, composer visibility, no horizontal overflow, keyboard/label semantics, and axe critical/serious findings.
- **Recovery:** API/provider unavailable, WebSocket disconnect, stale tasks, timeouts, invalid responses, and duplicate submissions.

## Responsive matrix

The authenticated chat layout is asserted at 320×700, 360×800, 390×844, 430×932, 768×1024, 1024×768, 1366×768, and 1920×1080. At each size the composer must remain inside the viewport, history must retain usable height, and the document must not overflow horizontally.

## Safety gates

- Never print `.env`, database URLs, cookies, tokens, API keys, or private archive contents.
- Never enable production AI or send owner conversations to Gemini.
- Never migrate, seed, truncate, or clean production.
- Public checks are GET-only and do not register users, create rooms, or send messages.
- A function or route existing in source is **IMPLEMENTED**, not automatically **VERIFIED**.
