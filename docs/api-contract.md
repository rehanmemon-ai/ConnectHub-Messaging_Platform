# ConnectHub API and WebSocket Contract

| Metadata | Value |
|---|---|
| Project | ConnectHub |
| Document title | API and WebSocket Contract |
| Status | Draft — Pending Project Owner Review |
| Version | 0.1 |
| Date of preparation | 2026-11-16 |

## 1. Conventions

**Implementation boundary (complete backend milestone):** identity, room/membership, messaging, notification, AI, and WebSocket operations documented below are implemented. The React feature UI is not. This specification remains a draft pending owner review.

REST base path is `/api/v1`; JSON uses `snake_case`, UTF-8, UUID strings, and ISO 8601 UTC timestamps (`Z` in examples). Protected requests use the HttpOnly session cookie. Mutating cookie-authenticated HTTP requests also require the chosen CSRF proof. Responses never contain passwords, password hashes, raw session tokens, or token hashes.

Fields not declared by an input schema are rejected using strict schema configuration such as Pydantic `extra="forbid"`. Validation errors use the common envelope. History access is standardized: invalid authentication is `401`, an existing room accessed by a non-member is `403`, a nonexistent room is `404`, and a current member receives `200`.

### Shared shapes

```json
{
  "user": {
    "id": "2f5719dc-b6cd-47a7-96e3-d572fc66ad2d",
    "username": "rehan",
    "display_name": "Rehan",
    "created_at": "2026-11-16T00:00:00Z"
  }
}
```

```json
{
  "room": {
    "id": "e3a927a2-98b8-4ce2-a239-42a3aaf8469f",
    "name": "Python Lounge",
    "description": "Python learners and builders",
    "membership": {"role": "member", "joined_at": "2026-11-16T00:01:00Z"},
    "created_at": "2026-11-16T00:00:30Z"
  }
}
```

The `membership` value is `null` for a discoverable room the caller has not joined. Email appears only in the authenticated user's own profile, not public sender/room projections.

### Error envelope

```json
{
  "error": {
    "code": "room_membership_required",
    "message": "You must join this room before accessing its conversation.",
    "details": [],
    "request_id": "req_illustrative"
  }
}
```

`code` is stable and machine-readable; `message` is safe for users; `details` contains field-level items such as `{"field":"email","code":"invalid_format","message":"Enter a valid email."}`. `request_id` supports sanitized log correlation. Stack traces, SQL, secrets, and internal exception text are never returned.

| Status | Meaning |
|---:|---|
| 400 | Malformed request/cursor or violated operation rule not represented below |
| 401 | Missing, expired, revoked, or invalid session |
| 403 | Authenticated but not authorized, including CSRF/origin failure where disclosure is safe |
| 404 | Resource does not exist |
| 409 | Unique/conflicting state: identity exists, duplicate membership, owner cannot leave |
| 422 | Schema or field validation failure |
| 429 | Configured request/login limit exceeded; may include `Retry-After` |
| 500 | Sanitized unexpected server failure |

## 2. REST endpoint summary and contracts

All response examples are illustrative. Successful `POST` responses creating a resource use `201`; ordinary reads/updates use `200`; logout, leave, and delete use `204` with no body.

### Authentication

#### `POST /api/v1/auth/register`

- Purpose: create an account. Authentication: none. Authorization: public; rate-limited.
- Body: `username` (1–50 after normalization), `email`, `password` (policy set in security spec), `display_name` (1–100).
- Example: `{"username":"Rehan","email":"rehan@example.test","password":"correct horse battery staple","display_name":"Rehan"}`
- Success `201`: own-user shape including normalized `username`, `email`, `display_name`, and timestamps. Registration does not implicitly promise login unless Task 3 explicitly chooses it; proposed contract requires a separate login.
- Errors: `409 username_taken|email_taken`; `422 validation_error`; `429 rate_limited`; safe `500`.

#### `POST /api/v1/auth/login`

- Purpose: create a browser session. Authentication: none. Authorization: public; rate-limited.
- Body: `identifier` (username or email) and `password`.
- Example: `{"identifier":"rehan@example.test","password":"correct horse battery staple"}`
- Success `200`: own-user shape; response sets the configured HttpOnly session cookie. The raw token is not in JSON.
- Errors: `401 invalid_credentials` with a generic message; `422`; `429`; `500`.

#### `POST /api/v1/auth/logout`

- Purpose: idempotently revoke a valid current session when present and expire session and CSRF cookies. Valid cookie-authenticated revocation requires CSRF proof.
- Body: none. Success is always `204` when the session is absent, expired, revoked, or successfully revoked; associated local sockets close when identifiable.
- Errors: `403 csrf_failed` only when a currently valid cookie-authenticated session is being revoked without valid proof; safe `500`.

### User profile

#### `GET /api/v1/users/me`

- Purpose: retrieve the current profile. Authentication required; self only.
- Success `200`: `{"user":{"id":"...","username":"rehan","email":"rehan@example.test","display_name":"Rehan","created_at":"...","updated_at":"..."}}`.
- Errors: `401`, `500`.

#### `PATCH /api/v1/users/me`

- Purpose: update allowed profile fields. Authentication and CSRF required; self only.
- Body: at least one of `username` or `display_name`; omitted values are unchanged. Email is immutable. Password change/recovery and email verification are outside the MVP.
- Example: `{"display_name":"Rehan V."}`. Success `200`: updated own-user shape.
- Errors: `401`; `403 csrf_failed`; `409 username_taken`; `422`; `500`.

#### `GET /api/v1/users/me/rooms`

- Purpose: list the current user's memberships. Authentication required; self only.
- Query: opaque cursor holding `(joined_at, room_id)` and `limit` (default 50, max 100), ordered `(joined_at DESC, room_id DESC)`.
- Success `200`: `{"items":[{"room":{...},"role":"owner","joined_at":"..."}],"next_cursor":null}`.
- Errors: `400 invalid_cursor`; `401`; `422`; `500`.

### Rooms

#### `GET /api/v1/rooms`

- Purpose: discover public rooms. Authentication required; any authenticated user.
- Query: optional trimmed `search` (maximum 100 characters), opaque `(created_at, id)` cursor, and `limit` (default 50, max 100), ordered descending. Search is case-insensitive substring matching on room name; `%`, `_`, and the escape character are safely escaped before `LIKE`/`ILIKE`. No conversation data is returned.
- Success `200`: `{"items":[{"id":"...","name":"Python Lounge","description":"...","membership":null,"created_at":"..."}],"next_cursor":null}`.
- Errors: `400 invalid_cursor`; `401`; `422`; `500`.

#### `POST /api/v1/rooms`

- Purpose: create a room and owner membership atomically. Authentication and CSRF required.
- Body: `name` (1–100) and `description` (0–500).
- Example: `{"name":"Python Lounge","description":"Python learners and builders"}`.
- Success `201`: room shape with caller membership role `owner`. A failed owner-membership insert rolls back the room.
- Errors: `401`; `403 csrf_failed`; `422`; `429`; `500`.

#### `GET /api/v1/rooms/{room_id}`

- Purpose: inspect public room metadata. Authentication required; any authenticated user. It does not return messages or member-sensitive data.
- Path: valid room UUID. Success `200`: room shape; membership is caller-specific or `null`.
- Errors: `401`; `404 room_not_found`; `422 invalid_room_id`; `500`.

#### `POST /api/v1/rooms/{room_id}/membership`

- Purpose: join a public room. Authentication and CSRF required.
- Body: none; clients cannot choose a role. Success `201`: `{"membership":{"room_id":"...","user_id":"...","role":"member","joined_at":"..."}}`.
- Errors: `401`; `403 csrf_failed`; `404`; `409 already_a_member`; `422`; `500`. A unique constraint resolves join races safely.

#### `DELETE /api/v1/rooms/{room_id}/membership`

- Purpose: leave as a normal member. Authentication, current membership, and CSRF required.
- Success `204`; prior messages remain. Local sockets for that user/room are closed.
- Errors: `401`; `403 csrf_failed|room_membership_required`; `404`; `409 owner_cannot_leave`; `422`; `500`.

#### `DELETE /api/v1/rooms/{room_id}`

- Purpose: permanently delete an owned room under the approved MVP policy. Authentication, owner role, and CSRF required.
- Success `204`; memberships/messages are removed atomically and local room sockets close.
- Errors: `401`; `403 room_owner_required|csrf_failed`; `404`; `422`; `500`.
- **Implementation status:** permanent owner-controlled deletion was approved for Task 3 and is implemented. A future deliberate confirmation UX is still required but cannot replace backend authorization.

### Messages

#### `GET /api/v1/rooms/{room_id}/messages`

- Purpose: retrieve persistent history. Authentication and current room membership required.
- Query: `limit` (default 50, maximum 100) and optional opaque `before` cursor.
- Success `200`:

```json
{
  "items": [
    {
      "id": "046e77df-cfb1-47fa-9a62-f706926d0e09",
      "room_id": "e3a927a2-98b8-4ce2-a239-42a3aaf8469f",
      "sender": {"id": "2f5719dc-b6cd-47a7-96e3-d572fc66ad2d", "username": "rehan", "display_name": "Rehan"},
      "content": "Hello everyone!",
      "created_at": "2026-11-16T00:02:00Z"
    }
  ],
  "next_cursor": "opaque_cursor_or_null"
}
```

- Ordering: `(created_at DESC, id DESC)`. `before` selects rows strictly older than the cursor tuple. The cursor is not authorization.
- Errors: `400 invalid_cursor`; `401`; `403 room_membership_required` for an existing room; `404 room_not_found`; `422`; `500`.

There is no REST message-creation endpoint in the MVP.

## 3. Authorization matrix

| Operation | Visitor | Authenticated non-member | Member | Owner |
|---|---:|---:|---:|---:|
| Register/login | Yes | Yes | Yes | Yes |
| View/update own profile | No | Yes | Yes | Yes |
| Discover/view public room metadata | No | Yes | Yes | Yes |
| Create room | No | Yes | Yes | Yes |
| Join room | No | Yes | Already joined | Already joined |
| Leave room | No | No | Yes | No |
| Read history/open room socket/send | No | No | Yes | Yes |
| Delete room | No | No | No | Yes |

“Authenticated non-member” is a state, not a role stored in the membership table. Every protected decision is enforced by the backend using current database state.

## 4. WebSocket protocol

### Handshake

Connect to `/ws/rooms/{room_id}` using the browser's established session cookie. The server validates the UUID, explicit Origin allowlist, live session, room existence, and current membership **before acceptance**. The token must not appear in the URL or subprotocol. Missing/invalid session is rejected as authentication failure, nonexistent room as not found where supported, existing-room non-membership as forbidden, and only an authorized member is accepted.

On acceptance:

```json
{
  "type": "connection.ready",
  "room_id": "e3a927a2-98b8-4ce2-a239-42a3aaf8469f",
  "user": {"id": "2f5719dc-b6cd-47a7-96e3-d572fc66ad2d", "username": "rehan"}
}
```

No presence guarantee is implied.

### Client event

The only initial client event is:

```json
{"type":"message.send","content":"Hello everyone!"}
```

The frame is limited to 16 KiB and the object must match its strict schema and 4,000-character content limit. Sender ID, username, role, message ID, room ID, timestamp, and every other unexpected field are rejected; none is trusted.

### Server events

Persisted messages use the same message projection as REST:

```json
{
  "type": "message.created",
  "message": {
    "id": "046e77df-cfb1-47fa-9a62-f706926d0e09",
    "room_id": "e3a927a2-98b8-4ce2-a239-42a3aaf8469f",
    "sender": {"id": "2f5719dc-b6cd-47a7-96e3-d572fc66ad2d", "username": "rehan", "display_name": "Rehan"},
    "content": "Hello everyone!",
    "created_at": "2026-11-16T00:02:00Z"
  }
}
```

Protocol errors are safe and machine-readable:

```json
{
  "type": "error",
  "error": {"code": "message_too_long", "message": "Messages cannot exceed 4000 characters.", "recoverable": true}
}
```

Codes include `invalid_json`, `invalid_event`, `invalid_content`, `message_too_long`, `authentication_required`, `session_expired`, `room_membership_required`, `room_deleted`, `rate_limited`, and `internal_error`. Authentication/authorization loss and repeated malformed/abusive events are terminal; validation errors may be recoverable. Close codes and reason text must be documented and tested in Task 4 without sensitive detail.

## 5. Persistence, broadcast, and failure semantics

For every `message.send`, the backend authenticates the current connection/session as required, verifies current membership, validates content, creates the message, commits the transaction, builds the canonical shared projection, and only then broadcasts `message.created` to process-local room connections. Commit failure produces a safe error and no broadcast.

Delivery is at-most-live-attempt per connected socket, not exactly once. A client can disconnect after commit but before receipt, or receive the event before its acknowledgement state is known. The database is authoritative. Clients deduplicate by message UUID and retrieve history after connection loss.

## 6. Revocation, cleanup, and reconnection

- Logout/revocation: new handshakes and later authenticated actions fail; identifiable local sockets are closed. The implementation must not rely solely on cookie clearing because an accepted socket no longer performs an HTTP handshake.
- Session expiry: record an expiry deadline at acceptance and close at/after it; an accepted socket does not automatically become invalid merely because its HTTP cookie expires. No messages are processed after authorization loss.
- Membership removal: close that user's local room sockets and deny later events/history.
- Room deletion: close all local room sockets with a safe terminal reason.
- Disconnect: remove the socket in `finally`; one failed send must not corrupt the room registry.
- Reconnect: use bounded exponential backoff with jitter, reset after a stable connection, stop/reduce retries for terminal authorization errors, and provide user-visible status.
- Recovery: after reconnection, fetch REST history using the last known ordering position/current newest page and deduplicate by ID.

The connection manager is in-memory and single-process. Multiple backend workers would have separate registries and incomplete broadcasts; the MVP deployment must use one backend process. Cross-instance Pub/Sub is deferred.

## 7. Contract verification

The automated suite covers REST authentication/authorization/error paths, stable cursor ties, sender authority, idempotency, real PostgreSQL row locks, WebSocket origin/session/membership checks, malformed/frame-size close paths, persistence-before-broadcast, local multi-connection cleanup, and mocked-provider AI persistence/search behavior. Distributed broadcast is not claimed.

Message send and membership removal acquire conflicting PostgreSQL locks on the same membership row; both commit orderings are covered against PostgreSQL. Health endpoints are unversioned: `GET /health/live` is process-only, while `GET /health/ready` safely checks database connectivity.

## 8. Complete backend extension

The following implemented routes extend the original v0.1 summary. All `/api/v1` operations require a live session unless explicitly documented as pre-authentication. Cookie-authenticated mutations require the session-bound CSRF header/cookie proof and trusted Origin.

| Operation | Route | Authorization / result |
|---|---|---|
| Send message | `POST /api/v1/rooms/{room_id}/messages` | Member; `201`; strict `{client_id, content}`; replay returns the existing message |
| History | `GET /api/v1/rooms/{room_id}/messages` | Member; stable opaque `before` cursor |
| Text search | `GET /api/v1/rooms/{room_id}/messages/search?q=` | Member; literal wildcard-safe substring search |
| Read position | `PUT /api/v1/rooms/{room_id}/read-position` | Member; own monotonic cursor only |
| Read receipts | `GET /api/v1/rooms/{room_id}/read-receipts` | Member |
| Members | `GET /api/v1/rooms/{room_id}/members` | Member |
| Remove member | `DELETE /api/v1/rooms/{room_id}/members/{user_id}` | Owner; owner cannot be removed |
| Invite | `POST /api/v1/rooms/{room_id}/invitations` | Owner of private room |
| Sent invitation history | `GET /api/v1/rooms/{room_id}/invitations` | Current owner; cursor-paginated, all statuses |
| Revoke invitation | `DELETE /api/v1/rooms/{room_id}/invitations/{invitation_id}` | Owner |
| Pending invitations | `GET /api/v1/users/me/invitations` | Invitee |
| Accept/decline | `POST /api/v1/invitations/{id}/accept` or `/decline` | Invitee; one terminal transition |
| Notifications | `GET /api/v1/notifications`, `/unread-count` | Owner of notification |
| Read notification(s) | `POST /api/v1/notifications/{id}/read`, `/read-all` | Owner of notification |
| Summary | `POST /api/v1/rooms/{room_id}/summaries` | Member; `503 ai_not_configured` when AI is disabled |
| Semantic search | `POST /api/v1/rooms/{room_id}/messages/semantic-search` | Member; bounded room-scoped candidates |
| Embedding state | `GET /api/v1/rooms/{room_id}/embeddings/status` | Member |
| Backfill | `POST /api/v1/rooms/{room_id}/embeddings/backfill` | Owner; bounded request |

AI contract clarification (2026-11-17): summary responses include `prompt_version`, `source_truncated`, and `input_characters`. Embedding status includes the active `embedding_profile` and `candidate_limit`. Semantic-search responses distinguish `total_messages`, active-profile `indexed_messages`, `unindexed_messages`, `indexed_candidates`, `candidate_limit`, `candidate_window_truncated`, and active-profile `failed_jobs`. A message is not “unindexed” merely because it falls outside the candidate window. Backfill returns `409 ai_disabled` unless AI is enabled and `409 ai_backfill_disabled` unless the explicit backfill gate is enabled.

Private rooms are excluded from discovery and return `404` to nonmembers for direct detail, membership, history, member, AI, and initial room-WebSocket access.

### Implemented WebSocket v1

Connect to `/ws` for explicit subscriptions or `/ws/rooms/{room_id}` for an initial authorized subscription. Authentication uses `connecthub_session`; an explicit configured `Origin` is mandatory. Query-string credentials are unsupported.

Client events are strict discriminated JSON objects: `room.subscribe`, `room.unsubscribe`, `message.send`, `typing.start`, `typing.stop`, `read.update`, and `ping`. Server events include `connection.ready`, `room.subscribed`, `room.unsubscribed`, `message.created`, `message.replayed`, `typing.started`, `typing.stopped`, `read_receipt.changed`, `presence.changed`, `notification.created`, membership/room revocation events, `pong`, and the shared `error` envelope.

Application frames are capped at 16 KiB. Three malformed events close with `1008`; oversized frames close with `1009`. Origin/session/initial-room checks happen before `accept`, so a real ASGI server rejects those handshakes at HTTP level; the application reasons are `origin_denied`, `authentication_required`, and `room_unavailable`. After acceptance, an expired session closes with `4401`, while connection-limit rejection uses `4429`. Delivery and presence are process-local in the approved single-process MVP.
