# ConnectHub demo script

## Safety prerequisite

Use synthetic identities and an explicitly authorized disposable database ending in `_demo`. Do not create it automatically, truncate `connecthub_dev`, or use `connecthub_test` as a presentation database. Keep AI disabled unless the owner has approved provider terms and synthetic-only calls.

## Two-to-three minute product walkthrough

1. Register two synthetic users and restore one browser session after refresh.
2. Discover and join a public room; create a private room in the other browser.
3. Invite the second user, accept, and show outsider concealment.
4. Send messages in both windows; demonstrate typing, presence, read receipts, retry deduplication, and notifications.
5. Search exact text. Explain that semantic search and summary return a safe unavailable state while AI is disabled.
6. Logout and show session revocation.

## Five-minute technical walkthrough

Trace browser → FastAPI → membership lock → PostgreSQL commit → in-process broadcast. Explain opaque session digests and CSRF, then show migration 0003, the profiled job lifecycle, query/document task types, candidate-bounded cosine ranking, synthetic metrics, and privacy gates. End with the one-worker and non-production limitations.

## Optional approved AI segment

Use only synthetic messages. Enable AI, automatic indexing, or owner backfill explicitly for the demo process; never edit or show a real key. Show profile status, wait for indexing, compare exact and semantic paraphrase results, generate a bounded summary, and disclose external processing. Restore AI-disabled configuration afterward.

## Recording storyboard

Capture title (5s), auth (20s), public/private room flow (40s), real-time behavior (35s), search/AI-disabled state (25s), architecture/evaluation (35s), and limitations (20s). A recording and real screenshots are **NOT RUN** in this milestone.
