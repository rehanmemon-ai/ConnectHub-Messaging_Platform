# ConnectHub Security Review

Status: **IMPLEMENTED controls reviewed; independent penetration test NOT RUN**  
Review date: 2026-11-17  
Target: the current modular-monolith backend, React client, PostgreSQL schema, and deployment example.

## Scope and method

This is a source review and local verification against the risk areas represented by OWASP ASVS 5.0 and the OWASP session, CSRF, and WebSocket guidance. It is not an ASVS certification, external penetration test, or production infrastructure review. ASVS 5.0 is the current stable OWASP verification framework: <https://asvs.owasp.org/>.

## Threat model

| Asset / boundary | Principal threats | Current controls | Residual risk |
|---|---|---|---|
| Passwords and accounts | Credential stuffing, enumeration, stolen hashes | Argon2id, dummy verification, generic login failure, process rate limits | Rate limits are per process and not durable across replicas |
| Session cookie | Theft, fixation, replay | 32-byte random token, digest-only database storage, HttpOnly, SameSite=Lax, production Secure requirement, server-side expiry/revocation | Production should use a `__Host-` cookie name; no global session-management UI |
| State-changing HTTP | CSRF and cross-origin abuse | Session-bound HMAC CSRF token, constant-time comparison, exact Origin allowlist, JSON content-type enforcement | Reverse proxy must preserve the real origin and HTTPS scheme |
| Rooms and messages | IDOR, private-room discovery, unauthorized mutation | Membership/owner checks in services, private-room 404 concealment, database foreign keys/checks | Authorization must remain on every new route; test it before release |
| WebSocket | Cross-site hijacking, stale session, subscription escalation, flood | Exact Origin, live session check on each event, room membership checks, frame/malformed/connection/queue/idle bounds | Single-process connection manager; multi-replica fan-out is unsupported |
| Browser | XSS, clickjacking, MIME confusion, data exfiltration | React text escaping, no raw HTML rendering, CSP in production, frame denial, nosniff, referrer/permissions/cross-origin headers | CSP has only been source/test reviewed, not exercised behind a real TLS edge |
| Database | Injection, overprivilege, accidental destructive tests | SQLAlchemy bound expressions, non-superuser app role, `_test` identity guard, separate URLs | Backups and provider encryption/retention remain operator responsibilities |
| AI provider | Message disclosure, prompt abuse, provider retention | Disabled by default, bounded inputs/timeouts, API key in secret setting, graceful unavailable path | Room message content leaves the application when enabled; consent/notice is required |
| Logs | Token/message/credential disclosure | Structured request IDs and deliberately redacted readiness errors; message bodies/tokens not logged | Reverse-proxy/provider logs require separate review |

## Verified control observations

- Session tokens are generated from a cryptographically secure source and only their digest is stored. This aligns with OWASP's recommendation to retain a one-way verifier when session-store disclosure is in scope: <https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html>.
- Cookies use HttpOnly for the session and SameSite=Lax; production configuration refuses non-Secure cookies. SameSite is defense in depth and does not replace the implemented CSRF token.
- Password verification uses Argon2id and a dummy hash for unknown users. Authentication error copy does not distinguish username/email existence.
- Mutating API operations require the session-bound CSRF header and an explicitly allowed Origin. CORS contains explicit origins and methods, including the read-position `PUT` route.
- WebSocket sessions validate Origin, session state, subscriptions, membership, event schemas, frame size, malformed-event count, idle timeout, connection count, and outbound queue size. The current OWASP WebSocket guidance specifically emphasizes exact Origin validation, ongoing session checks, authorization per action, message limits, and avoiding sensitive logs: <https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html>.
- The browser renders message content as React text. There is no `dangerouslySetInnerHTML` message path.
- Baseline headers are applied on all API responses. CSP and HSTS are enabled only for `APP_ENV=production` so local HTTP development remains usable.

## Findings and disposition

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| SEC-001 | High | No genuine multi-user browser journey previously guarded the HTTP/WebSocket authorization boundary | **REMEDIATED locally:** Playwright suite added; final pass recorded in release readiness |
| SEC-002 | High | No application CSP/HSTS or baseline hardening headers | **REMEDIATED:** production CSP/HSTS and common response headers added |
| SEC-003 | Medium | WebSocket disconnects raised the newer Starlette `WebSocketDisconnected` outside the existing catch | **REMEDIATED:** both disconnect exception types are handled and cleanup still runs |
| SEC-004 | Medium | Owner-sent invitation history existed only in current client memory | **REMEDIATED:** owner-authorized persisted invitation listing added |
| SEC-005 | Medium | Process-local rate limits do not coordinate multiple workers/replicas | **ACCEPTED for single-instance release;** use a shared limiter before horizontal scale |
| SEC-006 | Medium | AI enablement transmits room content to a third party | **REQUIRES OWNER DECISION:** keep disabled unless privacy notice, lawful basis/consent, and provider settings are approved |
| SEC-007 | Low | Production cookie names do not use the `__Host-` prefix | **RECOMMENDED:** deploy with `SESSION_COOKIE_NAME=__Host-connecthub_session` and a similarly scoped CSRF name after browser acceptance testing |

## AI data handling

When AI is enabled, summary prompts and message text used for embeddings are sent to the configured Gemini API. The application does not use Files, explicit caching, Interactions, Search/Maps grounding, or provider datasets. Google's terms effective 2026-03-23 state that unpaid-service content may be used for product improvement and human review, while paid-service prompts/responses are not used to improve products. Paid-service abuse-monitoring data is currently documented as retained for 55 days unless approved zero-data-retention sanitization applies: <https://ai.google.dev/gemini-api/terms>, <https://ai.google.dev/gemini-api/docs/usage-policies>, and <https://ai.google.dev/gemini-api/docs/zdr>. Optional developer logs can be configured for 7, 14, 28, or 55 days and datasets can persist longer; they must remain disabled unless expressly approved: <https://ai.google.dev/gemini-api/docs/logs-policy>.

Default release decision: keep `AI_ENABLED=false`. Enabling it requires an owner-approved privacy notice and confirmation of billing tier, logging, region, retention, deletion, and subprocessor terms.

## Remaining verification

- External penetration test: **NOT RUN**.
- TLS edge, proxy header behavior, CSP in a deployed browser, provider firewall, secret manager, encryption-at-rest, and backup retention: **NOT RUN** because no hosting platform is authorized.
- Dependency CVE checks are recorded separately in `RELEASE_READINESS.md`.

