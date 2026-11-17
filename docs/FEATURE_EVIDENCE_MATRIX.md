# ConnectHub feature-to-evidence matrix

Current evidence date: 2026-11-17. Status labels are intentionally specific.

| Feature | Source | Automated evidence | Browser/public evidence | Status / limitation |
|---|---|---|---|---|
| Registration, login, logout, session restore, CSRF | `backend/app/identity`, `frontend/src/features/auth` | identity API + App/auth tests | Playwright registration and refresh | **VERIFIED IN ISOLATED E2E** |
| Password visibility | `AuthPages.tsx` | `auth-pages.test.tsx` | registration exercised in E2E | **VERIFIED LOCALLY** |
| Profile read/update | identity service/router, profile page | identity API and frontend flow tests | not separately captured | **VERIFIED LOCALLY** |
| Public rooms/discovery/join | rooms routers/services and room pages | rooms integration + frontend flows | independent owner/member Playwright journey; screenshot 04 | **VERIFIED IN ISOLATED E2E** |
| Private rooms/invitations | private-room service and invitation views | private-room integration tests | send, inspect, accept, persistence, outsider denial; screenshots 07–09 | **VERIFIED IN ISOLATED E2E** |
| Ownership/member authorization | room service membership locking | room/private-room integration tests | private outsider receives 404 | **VERIFIED IN ISOLATED E2E** |
| Durable messages/history | messaging service/router and `ChatPage.tsx` | messaging/database tests + frontend flows | refresh persistence; screenshots 03, 05, 06 | **VERIFIED IN ISOLATED E2E** |
| Idempotent sends | messaging service/client UUID | messaging tests | duplicate client ID returns one message ID | **VERIFIED IN ISOLATED E2E** |
| WebSocket delivery/reconnect | realtime router/manager/client | WebSocket integration and manager unit tests | independent live clients | **VERIFIED IN ISOLATED E2E** |
| Presence/typing/read receipts | realtime + read-position services/UI | backend realtime/messaging and frontend flow tests | core multi-user route exercised; visual details not separately recorded | **VERIFIED LOCALLY** |
| Scroll/history UX | `ChatPage.tsx`, `scroll.ts` | helper and frontend flow tests | eight viewport assertions; screenshots 13–14 | **VERIFIED IN ISOLATED E2E** |
| Notifications | notifications service/router/page | backend integration and frontend mutation tests | no dedicated final screenshot | **VERIFIED LOCALLY** |
| Exact message search | messaging search + search page | messaging/frontend tests | exact phrase after refresh; screenshot 11 | **VERIFIED IN ISOLATED E2E** |
| Summary service/cache | `backend/app/ai/service.py`, provider | AI integration/provider tests | safe disabled state screenshot 10 | **IMPLEMENTED; LIVE PROVIDER NOT RUN** |
| Embedding worker/jobs | `backend/app/ai/worker.py`, models/migration | AI integration and profile-isolation tests | no live Gemini call | **VERIFIED WITH FAKES; LIVE NOT RUN** |
| Semantic retrieval | AI service/router, versioned profile | integration tests + 60-query offline baseline | disabled state only publicly | **IMPLEMENTED; REAL GEMINI QUALITY NOT RUN** |
| Accessibility | semantic UI/primitives/styles | Testing Library assertions | axe: zero critical/serious findings in desktop/mobile scenario | **VERIFIED IN ISOLATED E2E** |
| Responsive UI | shell/chat styles | viewport helper tests | 320×700 through 1920×1080 | **VERIFIED IN ISOLATED E2E** |
| Health and same-origin proxy | FastAPI health, Vite/Nginx proxy | config/build checks | backend, frontend, proxied readiness HTTP 200 | **VERIFIED ON PUBLIC DEPLOYMENT** |
| Favicon/metadata | `frontend/index.html`, `public/favicon.svg` | build/E2E request | public favicon still SPA fallback | **VERIFIED LOCALLY / NOT DEPLOYED** |
| Security/dependencies | config, auth, CI/manifests | 97 backend tests, audits, safe scan | no mutating public security test | **VERIFIED LOCALLY** |

Portfolio evidence is outside Git at `D:\_Rehan\ConnectHub-Portfolio-Assets`. Screenshot names in this table are synthetic E2E captures, not production data.
