# ConnectHub Production Owner Actions

**Status:** owner decision checklist; external access and public production remain **NOT AUTHORIZED / NOT RUN**.

Never paste credentials, database URLs, tokens, cookies, private keys, or provider API keys into chat, issues, documentation, or committed files. Use the selected provider's encrypted secret mechanism and owner-controlled password manager.

| # | Required action | Why | Responsible party / access or decision | Required evidence | Gate |
|---:|---|---|---|---|---|
| 1 | Select hosting provider and region | Determines data location, latency, ingress behavior, backup controls, and cost. | Owner chooses from `STAGING_OPTIONS.md`; privacy/legal reviewer accepts region and CDN routing. | Written provider/region decision and current product-availability capture. | Staging |
| 2 | Approve staging budget | Every practical dynamic backend and durable managed database option requires billing. | Owner approves monthly base, tax, FX, storage/bandwidth overage ceiling, and alert threshold. | Recorded ceiling and provider billing alert. | Staging |
| 3 | Provide authorized deployment-account access | Resources must be owned and recoverable by the owner, not by a coding assistant or personal ad-hoc account. | Owner creates account/team and grants least privilege through the provider; no secrets through chat. | Named account owner, operator roles, MFA, and recovery method. | Staging |
| 4 | Configure staging DNS/domain | A stable trusted origin is required for cookies, CSRF, Origin checks, HTTPS, and WSS. | Owner/DNS administrator controls a staging subdomain. | DNS records resolve only to the approved provider and ownership is documented. | Staging |
| 5 | Provision TLS and trusted reverse proxy | Secure cookies and WebSockets require verified HTTPS/WSS and correct forwarded scheme/host. | Provider plus deployment operator. | Valid certificate; HTTP redirects to HTTPS; WSS succeeds; proxy headers, CSP, HSTS, and secure cookie attributes verified. | Staging |
| 6 | Provision least-privilege production database | Prevents superuser use and separates staging/production data. | Database administrator/provider operator creates distinct database and application role. | Sanitized identity/privilege report; TLS connection; no superuser/CREATEDB/CREATEROLE; backup/PITR enabled. | Staging |
| 7 | Configure production secrets | The service requires a database URL, strong CSRF secret, exact origins, secure-cookie configuration, and optional provider key. | Authorized provider operator enters secrets directly into runtime-only encrypted settings. | Redacted key-name inventory, secret rotation owner/date, successful configuration validation; no `TEST_DATABASE_URL`. | Staging |
| 8 | Authorize isolated local restore-test database | Archive readability does not prove recoverability. | Local PostgreSQL administrator creates `connecthub_restore_test` and grants only the rehearsal privileges. | Positive database identity, empty/suitable target, authorization record. | Public production; recommended before staging data is valuable |
| 9 | Run restore rehearsal | Proves schema/data recovery and operator procedure. | Database administrator and release operator follow `BACKUP_RESTORE.md`; never restore over dev or production. | Successful `pg_restore`, revision/table/constraint/count checks, read-only smoke, timing/RPO/RTO, authorized cleanup. | Public production |
| 10 | Enable monitoring and assign alert ownership | A pilot needs detection and response, not only health endpoints. | Owner names an on-call recipient; operator configures platform and external alerts. | Readiness/5xx/latency/WebSocket/database/storage/deployment/billing alerts tested, with escalation contact. | Staging |
| 11 | Approve retention, deletion, and privacy policies | Account deletion/export, retention, backup expiry, and AI-derived erasure are not complete product workflows. | Owner with privacy/legal advice defines policy and user notice. | Published/approved notice, retention schedule, support process, subprocessor list, incident contact. | Public production; pilot must avoid real sensitive data until resolved |
| 12 | Approve Gemini processing or keep AI disabled | Enabling AI sends selected messages/search text to an external provider. | Owner/privacy reviewer evaluates account tier, logging, retention, region, deletion, training, and consent. | Explicit approval and user notice, or verified `AI_ENABLED=false`. | AI only; keep disabled for staging by default |
| 13 | Connect GitHub remote and run remote CI | Local source has no commits/remote; the workflow has never run in GitHub Actions. | Owner creates/chooses repository, reviews initial commit, branch protection, and Actions permissions. | Remote URL, reviewed commit SHA, passing backend/frontend/audit/Playwright jobs, retained logs. | Staging |
| 14 | Build and scan production images | Local Docker daemon is unavailable, so Dockerfiles were not built/run or scanned here. | CI or authorized container operator builds immutable images without secrets. | Image digests, SBOM, vulnerability scan, non-root/backend worker checks, container health and WebSocket proxy smoke. | Staging |
| 15 | Authorize controlled staging deployment | Provisioning changes external state and creates cost. | Owner gives explicit provider/region/budget/commit authorization. | Written approval tied to provider, region, budget, and commit/image digest. | Staging |
| 16 | Perform staging smoke and rollback tests | Local success cannot validate provider TLS, routing, database networking, secrets, or rollback. | Release operator with owner-approved test accounts. | HTTPS/WSS health/auth/room/message smoke, authorization checks, migration record, monitoring alert, application rollback, isolated backup restore. | Public production |
| 17 | Separately approve public production launch | A pilot decision is not permission to publish publicly. | Owner reviews all evidence and accepts residual risks. | Signed/recorded go decision, launch window, rollback owner, incident/privacy contacts. | Public production |

## Immediate next decision

The smallest concrete owner decision is: **approve Render Singapore at a planning ceiling of USD 20/month plus tax/overages for a controlled staging pilot, or select DigitalOcean at a planning ceiling of USD 30/month plus tax/overages after confirming Bangalore placement for the required dynamic services.** The ceiling intentionally exceeds the USD 13 and USD 20 base estimates so billing alerts can be set before provisioning.

After that decision, connect an owner-controlled GitHub repository and obtain one complete remote CI run. Only then should the owner authorize provider resource creation.

## Owner-operated GitHub connection procedure

These commands are **instructions for a later owner-authorized session**, not authorization to run them now. First create an empty private repository in the owner's GitHub organization with no generated README/license, enable MFA, and decide who may administer Actions and secrets. Then, from the project root:

```powershell
git status --short --branch
git remote -v
# Review every untracked file and confirm .env, .venv, .runtime, node_modules, and generated reports are excluded.
git remote add origin https://github.com/OWNER/CONNECTHUB_REPOSITORY.git
git add --all
git diff --cached --stat
git diff --cached --check
# Inspect the complete staged snapshot before authorizing the first commit.
git commit -m "Initial ConnectHub verified application"
git push -u origin main
```

Immediately configure branch protection/rulesets for `main`, require the `backend`, `frontend`, and `browser-e2e` checks, restrict force pushes/deletion, and keep workflow permissions read-only unless a reviewed job needs more. Confirm the Actions run uses the disposable CI PostgreSQL service, contains no repository secrets in logs, executes both npm audits, and finishes all three jobs successfully. Record the commit SHA and run URL as release evidence.
