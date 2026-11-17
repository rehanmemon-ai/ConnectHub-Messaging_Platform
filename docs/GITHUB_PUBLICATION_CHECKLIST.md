# GitHub publication checklist

Status: **owner approval required; no commit, remote, or push has occurred**.

## Before the first commit

- Review every untracked path with `git status --short` and `git ls-files --others --exclude-standard`.
- Confirm `.env`, `.venv`, `node_modules`, `.runtime`, logs, dumps/backups, Playwright output, `dist`, keys, and nested review ZIPs are ignored or intentionally excluded.
- Inspect `.env.example` for placeholders only. Search locally for credential patterns, connection URLs, private keys, cookies, personal emails, and machine-specific absolute paths. Do not upload source to an external scanner without approval.
- Decide whether `ConnectHub_Review_Files.zip` belongs outside the public repository; source files already exist and the archive is redundant.
- Review dependency lockfiles. Preserve the intentional empty root `package-lock.json`; do not invent a root npm workspace.
- Select a license using `LICENSE_DECISION.md`, or understand that no-license publication reserves all rights and restricts reuse.

Suggested local review commands (PowerShell):

```powershell
git status --short
git check-ignore -v .env .venv frontend/node_modules .runtime
git ls-files --others --exclude-standard
rg -n --hidden -g '!/.git/**' -g '!/.venv/**' -g '!frontend/node_modules/**' '(api[_-]?key|password|secret|BEGIN .*PRIVATE KEY)'
```

Review every match; pattern scans produce false positives and do not prove absence.

## Owner-authorized publication sequence

1. Create an owner-controlled GitHub repository with no generated README/license/gitignore.
2. Re-run local tests and secret review on the exact snapshot.
3. Explicitly select files, inspect `git diff --cached`, then create the initial commit only after owner approval.
4. Add the owner-supplied remote URL and verify it with `git remote -v`.
5. Push `main`, observe the real GitHub Actions run, and record its URL/result.
6. Require pull requests, passing CI, and protected-branch review as appropriate.
7. Tag a release only from a verified commit; attach no `.env`, dump, backup, runtime log, or unreviewed ZIP.

No exact `git add`, commit, or push command is executed or authorized by this document.
