# ConnectHub Staging Options

**Research date:** 2026-11-17  
**Decision status:** recommendation prepared; no provider account, billing, DNS, resource, or deployment action was authorized or performed.

## Workload assumptions

The estimates below describe a small controlled pilot: one always-on backend process, one static React site, one managed PostgreSQL database, up to roughly 25 pilot users, low concurrent WebSocket use, less than 5 GB monthly application egress, and less than 1 GB initial database data. AI remains disabled. Taxes, card FX fees, domains, unusual build usage, and overages are excluded.

INR conversions use the RBI-published FBIL reference rate of **₹94.1159 per USD on 2026-11-16** ([RBI current rates](https://www.rbi.org.in/)). They are planning estimates, not invoices.

## Recommendation summary

1. **Best low-cost practical pilot: Render, Singapore.** Use one paid 512 MB web service, one free static site, and the smallest paid Render Postgres plan. Estimated minimum: **USD 13/month, about ₹1,224/month**, before tax and overages.
2. **Best India-region alternative: DigitalOcean.** Use one fixed 512 MiB App Platform service, one free static component, and the smallest Managed PostgreSQL plan. Current published starting-price estimate: **USD 20/month, about ₹1,882/month**, before tax and overages. Confirm that the account offers the intended Bangalore placement for every dynamic component before purchase; Managed PostgreSQL is listed in BLR1, but placement must be proved during provisioning.

Render is the recommended first pilot because it is simpler and cheaper while meeting the one-process WebSocket topology. DigitalOcean is preferable when India data location or a clearer path to stronger infrastructure matters more than the approximately USD 7 monthly difference, subject to confirming component placement in the owner account.

## Option A — Render Singapore (recommended low-cost pilot)

| Area | Proposed configuration and evidence |
|---|---|
| Region | Backend and database in Singapore. Render lists Singapore as a service/datastore region and notes that changing region later requires creating and migrating to new resources ([regions](https://render.com/docs/regions), retrieved 2026-11-17). |
| Backend | Paid web service, 0.5 CPU / 512 MB class, **one instance only**, estimated USD 7/month. Deploy the backend Dockerfile or native Python service and bind the provider `PORT`. Do not enable horizontal autoscaling. |
| Frontend | Free Render Static Site on the global CDN, with SPA fallback and `/api`, `/health`, and `/ws` routing designed so browser traffic remains same-origin. A provider-specific routing proof is mandatory before pilot acceptance. |
| PostgreSQL | Paid 0.1 CPU / 256 MB Render Postgres at USD 6/month plus storage above the included amount. It is small, so connection-pool and memory behavior must be observed during the pilot. |
| WebSockets | Render web services explicitly support WebSocket connections, TLS termination, custom domains, and private regional networking ([web services](https://render.com/docs/web-services), retrieved 2026-11-17). Authenticated WSS and Origin validation still require staging tests. |
| Persistence/connections | The backend stays always-on on a paid plan and connects to PostgreSQL over the regional private network. Keep SQLAlchemy pooling at the current bounded settings and verify the database's connection cap. |
| Backups | Paid Render Postgres receives continuous backups and PITR. Hobby workspaces have a three-day PITR window; logical exports are retained seven days ([backups](https://render.com/docs/postgresql-backups), retrieved 2026-11-17). Keep an additional encrypted logical export under an owner-approved retention policy. |
| Secrets | Store database URL, CSRF secret, cookie/origin settings, and any future AI key in provider environment secrets. Never expose `TEST_DATABASE_URL` to staging. |
| TLS/domain | Managed TLS and custom domains are supported. Keep `COOKIE_SECURE=true`, use the final exact HTTPS origin, and test HTTPS/WSS, secure cookies, CSP, and proxy headers. |
| Monitoring | Configure readiness checks, deployment-failure notification, 5xx/readiness alerts, database storage/connection monitoring, and an external HTTPS uptime check. |
| Free-tier warning | The free web service is subject to free-instance-hour and other limits. Free Postgres expires after 30 days, has no backups, can restart, and is capped at 1 GB; it is **not acceptable** for the pilot ([free limits](https://render.com/docs/free), retrieved 2026-11-17). |
| Cost | Low pilot: USD 7 backend + USD 6 database + USD 0 static = **USD 13 / ~₹1,224 monthly**. A moderate step-up to a USD 25 2 GB backend plus USD 19 1 GB database is about **USD 44 / ~₹4,141**, before storage and bandwidth. Current pricing lists 5 GB Hobby bandwidth then USD 0.15/GB, and PostgreSQL storage at USD 0.30/GB ([pricing](https://render.com/pricing), retrieved 2026-11-17). |

### Render-specific risks

- The cheapest database has only 256 MB RAM and is suitable only for a deliberately small pilot.
- Singapore is the nearest offered region, not India; the owner must accept that data location.
- Hobby PITR is only three days, and the base workspace has limited included bandwidth.
- Static-site proxy/path behavior must be proved against the actual same-origin cookie and WebSocket design. If Render cannot provide the required unified ingress cleanly, serve the built frontend from the single backend web service or choose DigitalOcean; do not weaken cookie or Origin controls.

## Option B — DigitalOcean with Bangalore verification

| Area | Proposed configuration and evidence |
|---|---|
| Region | Dynamic App Platform components are available in Bangalore (`BLR`), while static content there is delivered through Cloudflare CDN ([App Platform availability](https://docs.digitalocean.com/products/app-platform/details/availability/), generated 2026-11-16). Managed database regional availability must be reconfirmed in the account before purchase. |
| Backend | One fixed shared 1 vCPU / 512 MiB App Platform service at USD 5/month. Fixed shared instances are limited to one container, which aligns with ConnectHub's process-local real-time state. |
| Frontend | One free static component on the global CDN. Configure same-origin ingress rules for `/api`, `/health`, and `/ws`, or serve the built frontend with the backend container if WebSocket ingress cannot be proven. |
| PostgreSQL | DigitalOcean Managed PostgreSQL, smallest published plan starting at USD 15/month. Do not use the USD 7 App Platform development database: it has no backups and is destroyed with the app. |
| WebSockets | App Platform accepts long-lived concurrent connections and WSS is supported through its HTTPS application domain; verify upgrade, idle/reconnect behavior, cookie forwarding, and Origin handling in staging. The platform does not cap concurrent app connections, but each consumes instance resources ([limits](https://docs.digitalocean.com/products/app-platform/details/limits/), last verified 2026-05-20). |
| Persistence/connections | App containers have ephemeral local filesystems. All durable state stays in Managed PostgreSQL; reconnect behavior must respect managed-database DNS changes. |
| Backups | Managed PostgreSQL provides daily backups and seven-day PITR. A restore creates a new cluster for isolation ([restore procedure](https://docs.digitalocean.com/products/databases/postgresql/how-to/restore-from-backups/), last verified 2026-07-31). The smallest single node is not highly available despite automated replacement. |
| Secrets | App Platform supports encrypted environment variables. Limit sensitive variables to runtime scope; users able to modify code or open the console remain trusted operators ([environment variables](https://docs.digitalocean.com/products/app-platform/how-to/use-environment-variables/), retrieved 2026-11-17). |
| TLS/domain | Static sites include automatic HTTPS, custom domains, and CDN. Validate final DNS, certificate, secure cookies, WSS, CSP, and proxy headers before pilot access. |
| Monitoring | Configure readiness and liveness checks, deploy/domain alerts, runtime logs, database metrics, billing alerts, and an external HTTPS monitor. |
| Free-tier warning | Only static sites are free. The USD 5 dynamic service and managed database require billing. App Platform's USD 7 development PostgreSQL has no default backup and is coupled to app deletion, so it is not a release database. |
| Cost | Low pilot: USD 5 backend + USD 15 managed database + USD 0 static = **USD 20 / ~₹1,882 monthly**. This is a planning minimum, not a quote; confirm node, storage, transfer, and tax in the account before approval ([App Platform pricing](https://www.digitalocean.com/pricing/app-platform), [DigitalOcean pricing](https://www.digitalocean.com/pricing), retrieved 2026-11-17). |

### DigitalOcean-specific risks

- The cheapest managed PostgreSQL cluster is single-node and is not highly available; a standby materially increases cost.
- App Platform static traffic may traverse Cloudflare even when the dynamic service is in Bangalore. The owner must include this in the data-location/privacy decision.
- Current PostgreSQL Standard plan changes limit larger Standard clusters and standby/read-only options; confirm available account plans at approval time.
- Same-origin WebSocket routing and cookies need an actual staging proof, not just product support documentation.

## Required staging topology

```text
Browser -- HTTPS/WSS --> provider edge / one public origin
                              |-- static React assets
                              |-- /api, /health, /ws --> exactly one FastAPI process
                                                         |
                                                         +--> regional managed PostgreSQL
                                                         +--> Gemini HTTPS only if later approved
```

- Exactly one backend process/instance. Multiple workers would split WebSocket broadcast, presence, and rate-limit state.
- Managed PostgreSQL is durable truth; no filesystem persistence is assumed.
- TLS terminates at a trusted provider edge and WSS is exercised end-to-end.
- Production secrets are runtime-only. AI stays `AI_ENABLED=false` until a separate privacy/provider approval.
- Monitoring must cover availability, 5xx, latency, WebSocket disconnects, database connections/storage, deployments, and billing.

## Exact owner actions before provisioning

1. Choose Render Singapore or DigitalOcean Bangalore and approve the monthly ceiling plus taxes/overages.
2. Approve the data region and, for DigitalOcean static delivery, the CDN/data-routing implications.
3. Create the provider account and billing method directly with the provider; do not send credentials through chat.
4. Connect an owner-controlled GitHub repository or approve a private image registry workflow.
5. Choose the staging hostname and control its DNS.
6. Provision the paid managed database and a least-privilege application role; record backup/PITR settings.
7. Add runtime secrets through the provider's encrypted configuration UI.
8. Deploy one backend instance and the static frontend/unified ingress.
9. Run migrations once, then verify HTTPS/WSS, health, authentication, room authorization, rollback, monitoring, backup, and isolated restore evidence.
10. Review the evidence and separately authorize any public production step.

No provider should be provisioned from this document alone. Prices and product availability must be rechecked in the selected account immediately before purchase.
