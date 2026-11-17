# ConnectHub Security Design

| Metadata | Value |
|---|---|
| Project | ConnectHub |
| Document title | Security Design |
| Status | Draft — Pending Project Owner Review |
| Version | 0.1 |
| Date of preparation | 2026-11-16 |

## 1. Objectives and trust boundaries

Security goals are to protect account credentials and sessions, prevent unauthorized room access and sender impersonation, preserve database integrity, minimize personal-data exposure, and fail without leaking internals. The browser and all client-provided fields are untrusted. FastAPI is the authorization boundary; PostgreSQL is authoritative persistent state. The network is untrusted until protected by HTTPS/WSS. Frontend visibility checks are usability only.

This design does not provide end-to-end encryption: the server processes message plaintext and PostgreSQL stores it. Access control, transport encryption, provider/database controls, and retention policies protect it.

## 2. Authentication and passwords

Registration normalizes username/email once under a documented policy, validates lengths/formats, relies on database uniqueness for races, and hashes passwords with Argon2id. Work factors must be selected and measured on the target laptop in Task 3 rather than copied blindly. Hash verification should support safe parameter upgrades on successful login.

Password policy should favor length (proposed 12–128 characters), allow password managers and spaces, avoid destructive trimming, reject known-invalid encodings/oversize input before expensive hashing, and never log values. Login failures use one generic response for nonexistent users and wrong passwords. Timing differences should be reduced with a dummy verification path where appropriate.

## 3. Database-backed sessions

Login generates a cryptographically secure opaque token with at least 256 bits of entropy. PostgreSQL stores only its 64-character lowercase SHA-256 hexadecimal digest; the raw token exists only in the browser cookie and transient server memory and is never logged or returned in JSON.

A session authenticates only when its token digest matches, it is not revoked, it has not expired, and its user remains valid. Recommended initial expiry is seven days from creation, configurable. Multiple sessions per user support browsers/devices. Logout is idempotent: revoke a valid current row when present, clear session and CSRF cookies, return `204` even if absent/expired/revoked, and close associated local sockets where tracked. CSRF proof is required when revoking a currently valid cookie-authenticated session.

No JWT or refresh-token system is required: database sessions provide direct revocation and suit a one-service architecture.

## 4. Cookie and CSRF controls

Production session cookie properties:

- `HttpOnly=true`; `Secure=true`; `SameSite=Lax` unless a stricter verified flow works.
- Host-only: omit `Domain` unless deployment proves it necessary.
- `Path=/`; explicit expiration aligned with the server session; suitable `__Host-` prefix where deployment permits.
- Never expose the token to JavaScript, JSON, URLs, or logs.

Local HTTP development may disable `Secure` only for localhost; production startup/config validation must prevent that setting under HTTPS deployment.

SameSite is defense-in-depth, not the sole CSRF control. State-changing REST calls use a signed session-bound double-submit token: generate a random nonce; sign with HMAC-SHA256 using a dedicated CSRF secret and current-session binding; place the token in a readable SameSite=Lax cookie; echo it in `X-CSRF-Token`; compare cookie/header and verify the signature and explicit Origin. Registration/login instead require strict pre-authentication Origin and content-type validation. No CSRF database table is added. Read-only requests remain side-effect free.

## 5. WebSocket security

Browser WebSockets authenticate through the established cookie—not query strings. Before `accept`, the endpoint validates an explicit scheme/host/port Origin allowlist, room UUID, live session, and current membership. Missing/`null` origins are rejected for the browser application unless a separately authenticated non-browser client is later designed.

The client event schema is strict (`extra="forbid"`) and bounded. The server derives user, role, room, IDs, and timestamp from trusted state. Each accepted socket records a session-expiry deadline because cookie expiry does not automatically invalidate an open connection. Each message path revalidates membership/current authority; logout/revocation, expiry, membership removal, and room deletion close identifiable local connections, and no later event is processed. Close reasons are safe.

Incoming application frames are limited to 16 KiB in addition to the 4,000-character message-content limit. Message rate, concurrent sockets per user, idle timeout, bounded outbound queues, and malformed-event limits are implemented as configurable single-process controls.

## 6. Authorization

Backend policy rules are: authenticated users may discover/create public rooms; only current members may read history/connect/send; ordinary members may leave; owners cannot leave; only the single owner may delete. Duplicate membership is prevented by the composite key. Every protected endpoint queries current trusted state, and service-level policies are shared rather than copied into UI or route code.

Response choices must not disclose protected conversation existence or membership beyond product needs. Database foreign keys and constraints supplement—but do not replace—policy checks.

## 7. Input, output, and injection controls

- Validate JSON shape, type, normalized length, UUIDs, pagination cursors, and content before persistence.
- Treat messages as plain text. React renders text normally; never inject message HTML or use unsafe HTML APIs. If links are later created, use a vetted parser and safe URL policy.
- Use SQLAlchemy parameter binding; do not construct SQL with user strings. Dynamic sort/filter choices use server allowlists.
- Encode output through JSON serializers and explicitly declared response models.
- Reject unexpected fields so clients cannot mass-assign roles, ownership, sender IDs, or timestamps.
- Set appropriate security headers and a restrictive Content Security Policy after testing the built frontend.

## 8. Rate and resource limiting

Rate-limit registration/login, room creation/join, message sends, and socket connections using conservative configurable rules. Return `429` and `Retry-After` where useful. Combine account and network signals carefully; IP alone can punish shared networks, and username-only keys permit targeted lockout. Password verification endpoints need particular CPU protection.

The initial limiter may be process-local because the deployment is one process. Its counters reset on restart and would not coordinate across instances; it is abuse resistance, not a distributed guarantee. This limitation must be logged/documented. Do not introduce Redis until multi-instance deployment is actually required.

## 9. Secrets, configuration, and database security

Secrets (database URL/password, session/CSRF hashing keys if used, allowed origins) come from deployment environment/secret facilities and never source control, frontend bundles, exception responses, or logs. Maintain an environment-variable reference with secret/non-secret classification and safe examples only. Validate required settings and refuse unsafe production combinations.

PostgreSQL uses a least-privilege application role; migration privileges should be separated where practical. Require encrypted database transport when crossing untrusted networks, verify certificates/provider configuration, restrict network access, configure conservative pools/timeouts, and create tested backups appropriate to hosting. Production data must not be copied into development casually. Test configuration must positively identify a disposable test database and refuse known production targets.

Dependencies are pinned/locked only after Task 2 compatibility checks; CI runs vulnerability and update review appropriate to Python/Node. Changes are reviewed rather than blindly upgraded.

## 10. Errors, logs, and sensitive data

Clients receive stable safe codes, user-appropriate messages, and correlation IDs. Unexpected exceptions become a generic `500`. Logs may include request ID, route/event type, result, timing, user/room UUID when justified, and exception class internally. They must exclude passwords, session/CSRF tokens, cookies, Authorization values, password/token hashes, full database URLs, message bodies, and unnecessary email/IP data. Sanitize newline/control characters and apply retention/access controls.

Security events include repeated login failures, denied room access, origin failures, malformed WebSocket events, rate-limit activation, session revocation, and privileged room deletion—without leaking secrets.

## 11. Threat-to-control matrix

| Threat | Required controls |
|---|---|
| Plaintext/weak password storage | Argon2id, measured parameters, no plaintext/logging |
| Session theft | High-entropy opaque token, stored hash, HTTPS, Secure/HttpOnly host-only cookie, expiry/revocation |
| CSRF | Session-bound CSRF proof, SameSite, Origin/Referer checks, side-effect-free GET |
| XSS | Plain-text rendering, no unsafe HTML, output serialization, tested CSP/security headers |
| SQL injection | Bound ORM queries and allowlisted dynamic query fields |
| Unauthorized room access | Central backend policies and current membership lookup |
| Fake sender/role | Derive identity/role/timestamps from session/database; reject extra fields |
| Cross-Site WebSocket Hijacking | Explicit Origin allowlist plus session and membership validation before accept |
| Invalid/oversized socket payload | Strict event schema, frame/content limits, error/close policy |
| Brute-force/CPU exhaustion | Generic login errors, process-local limits, bounded inputs, monitoring |
| Excessive connections | Per-user/network caps, handshake validation, cleanup, timeouts |
| Secret exposure | Environment secret handling, redaction, frontend separation, rotation procedure |
| Information leakage | Safe envelope/close reasons, concealed protected resources, sanitized logs |
| Uncommitted/forged message delivery | Validate, persist, commit, then broadcast canonical server object |
| Dependency compromise | Minimal dependencies, lock/review/audit in CI, supported releases |
| Data loss | Approved deletion policy, transaction boundaries, backups and restore testing |

## 12. Security testing requirements

Automated tests must cover password hashing/verification and non-exposure; normalization/uniqueness races; invalid/expired/revoked sessions; cookie flags; CSRF missing/invalid/valid cases; authentication and role matrix; ownership invariant; SQL/injection-like inputs; plain-text XSS payload rendering; safe error/log redaction; WebSocket Origin/session/membership rejection; fake sender fields; oversized/malformed events; persistence-before-broadcast; logout/membership removal/room deletion behavior; rate limits; and production-database/configuration guards.

Task 6 adds dependency review, static checks, manual authorization-flow review, configuration review, and focused abuse testing. Findings are recorded with severity and remediation evidence. No security claim is based only on a function existing.

## 13. Data retention, limitations, and future work

Messages persist after a member leaves but become inaccessible until rejoin. Owner-controlled one-transaction hard deletion of live room, membership, and message rows is APPROVED and later requires destructive UI confirmation. Provider backup retention is separate, so immediate backup erasure is not claimed. Account deletion/export, legal retention, and anonymization remain outside the MVP.

Known MVP limitations: one process; process-local rate counters and socket registry; no instantaneous cross-instance revocation; no end-to-end encryption; no private rooms/moderation; and unverified operational limits. Future improvements may include coordinated Pub/Sub/rate limiting, stronger device/session management, audit records, and formal retention workflows only when requirements justify them.

## 14. Current implementation boundary

Tasks 2 and 3 implement explicit-origin credentialed CORS, environment-driven configuration, safe readiness errors, request correlation, schema/test-target guards, Argon2id password hashing with a dummy invalid-login verification path and rehash support, 256-bit opaque tokens with SHA-256-only database storage, live session expiry/revocation checks, and HttpOnly SameSite=Lax session cookies.

Authenticated mutations validate a session-bound HMAC-SHA256 double-submit token and explicit Origin. Registration/login require an explicit trusted Origin and JSON content type. Production configuration refuses non-Secure cookies and API startup refuses a missing, placeholder, or shorter-than-32-character CSRF secret. Rate limits cover registration, login, and room creation using an in-process sliding window; this is an accepted single-process MVP limit, not distributed abuse protection.

Room authorization is derived from the current session and database membership. Atomic room/owner creation, owner-leave/removal prevention, owner-only hard deletion, and a shared membership-row `FOR UPDATE` convention are implemented. Message send derives sender identity from the session and locks membership. WebSockets validate Origin and the live database session, revalidate per event, check room membership, and revoke local session/room subscriptions on logout, removal, or deletion.

AI keys are accepted only through settings and sent in a request header; keys and full provider payloads are not logged. Summaries treat stored messages as untrusted quoted content and use a system instruction that rejects message-authored instructions. AI queries and candidates are scoped only after membership authorization. AI outage returns safe service errors and cannot roll back an already committed core message. Server-side plaintext processing means ConnectHub is not end-to-end encrypted.
## AI processing safeguards (implemented 2026-11-17)

External processing is deny-by-default. `AI_ENABLED`, automatic new-message indexing, and historical backfill are separate controls; changing only the first does not release old messages. Jobs and vectors carry a compatibility profile. Only owners can request bounded backfill, and the deployment must also explicitly enable it. Provider payloads contain message/query text only for the requested AI operation; logs contain safe metadata, not prompts, bodies, keys, cookies, room names, or vectors. Invalid/non-finite vectors are rejected and unexpected worker exceptions become bounded durable failures.
