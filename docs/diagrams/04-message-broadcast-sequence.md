# Message persistence and WebSocket broadcast

```mermaid
sequenceDiagram
  participant C as Client
  participant A as FastAPI
  participant D as PostgreSQL
  participant M as Local connection manager
  C->>A: message.send(client UUID)
  A->>D: lock membership; insert or find replay
  D-->>A: COMMIT message first
  A->>M: broadcast message.created
  M-->>C: event to subscribed local sockets
  Note over A,D: AI job is added only when AI and automatic indexing are explicitly enabled
```
