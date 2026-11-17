# Authentication and session lifecycle

```mermaid
sequenceDiagram
  participant B as Browser
  participant A as FastAPI
  participant D as PostgreSQL
  B->>A: register/login
  A->>D: verify Argon2id; store token digest + expiry
  A-->>B: HttpOnly session + signed CSRF cookie
  B->>A: mutation + Origin + CSRF header
  A->>D: validate live session digest
  A-->>B: authorized result
  B->>A: logout
  A->>D: revoke session
  A-->>B: clear cookies and close local sockets
```
