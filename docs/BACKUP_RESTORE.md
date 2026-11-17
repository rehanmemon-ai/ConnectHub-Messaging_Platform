# ConnectHub Backup and Restore

Status: **procedure IMPLEMENTED; isolated restore rehearsal BLOCKED pending an authorized disposable restore database**

## Scope

Back up PostgreSQL with PostgreSQL 18 client tools compatible with the server. The database contains account identifiers, password hashes, session digests, rooms, memberships, messages, notifications, and optional AI-derived summaries/embeddings. Treat backups as sensitive.

## Backup

Use a restricted environment where `DATABASE_URL` is injected from a secret manager and command output is not captured with the value:

```powershell
$backupDir = Join-Path $env:TEMP "connecthub-backups"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$backupPath = Join-Path $backupDir ("connecthub-{0:yyyyMMdd-HHmmss}.dump" -f (Get-Date))
pg_dump --format=custom --no-owner --no-privileges --file $backupPath --dbname $env:DATABASE_URL
pg_restore --list $backupPath | Select-Object -First 20
```

Never put the URL in shell history or logs. Encrypt backups at rest, restrict access, define retention, and test deletion. A successful `pg_dump` exit and readable archive list validate the archive structure but do not prove a restore.

## Isolated restore rehearsal

Creating the restore target is an **administrator-only, explicitly authorized operation**. The `connecthub_app` role intentionally cannot create databases. A local PostgreSQL administrator must first inspect for an existing name and create a separate target owned by the application role; never overwrite development, test, or production:

```powershell
# Run only by an authorized PostgreSQL administrator. Do not put a password in this script.
psql -U postgres -h 127.0.0.1 -p 5432 -d postgres -c "SELECT datname FROM pg_database WHERE datname = 'connecthub_restore_test';"

# Only if the query confirms that no such database already exists:
createdb -U postgres -h 127.0.0.1 -p 5432 --owner=connecthub_app connecthub_restore_test
```

The administrator must positively confirm the new identity and ownership. Then provide `RESTORE_DATABASE_URL` to the rehearsal shell through a secure process environment; do not save or print it. The release operator may restore the existing archive only into that approved `_restore_test` target:

```powershell
createdb connecthub_restore_test
pg_restore --exit-on-error --no-owner --no-privileges --dbname $env:RESTORE_DATABASE_URL $backupPath
psql $env:RESTORE_DATABASE_URL -c "SELECT version_num FROM alembic_version;"
psql $env:RESTORE_DATABASE_URL -c "SELECT count(*) FROM users; SELECT count(*) FROM rooms; SELECT count(*) FROM messages;"
```

Verify table counts, constraints, a read-only application smoke test, and the Alembic revision. Then remove the disposable restore database only with explicit owner authorization. The project role intentionally lacks `CREATEDB`; no restore target was authorized during the local review, so the rehearsal remains **BLOCKED**, not falsely passed.

Cleanup is also administrator-only and requires a separate explicit authorization after evidence has been retained:

```powershell
# Authorized administrator only; first verify that no rehearsal process is connected.
dropdb -U postgres -h 127.0.0.1 -p 5432 connecthub_restore_test
```

## Recovery decision

For logical corruption, prefer a forward correction or point-in-time recovery into an isolated database. Before replacing any live target, record the recovery point objective, preserve the damaged database, verify the restored copy, and obtain explicit approval.

