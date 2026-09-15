# Staging / UAT Infrastructure Provisioning Request

**Application:** PayU Visitor Management System (VMS)  
**Release:** `1.0.0-rc1`  
**Request type:** Staging / UAT only — **not production cutover**  
**Date:** 2026-08-27

---

## 1. Purpose

Provision a **production-like staging environment** so engineering can complete release validation currently blocked on infrastructure:

| # | Validation |
|---|------------|
| 1 | PostgreSQL live validation (`npm run test:postgres`) |
| 2 | Alembic migration validation (001 → 014) |
| 3 | PostgreSQL concurrency testing |
| 4 | Backup / restore rehearsal (`npm run pg:restore-rehearsal`) |
| 5 | Microsoft Entra ID SSO (browser UAT) |
| 6 | Microsoft Graph email (`npm run test:graph-live`) |
| 7 | ClamAV document scanning (`npm run test:clamav-live`) |
| 8 | Final operator browser UAT |
| 9 | `npm run production:check` |
| 10 | `npm run rc:check` |
| 11 | Final GO / NO_GO decision (`npm run closure:matrix`) |

**Current production decision:** `NO_GO` — application code and automated regression are ready; staging infrastructure is not available.

---

## 2. Application stack (no changes required)

| Layer | Technology |
|-------|------------|
| Frontend | React, TypeScript, Vite (port **7272** in local dev) |
| Backend API | FastAPI, Python (port **7273** in local dev) |
| ORM | SQLAlchemy |
| Migrations | Alembic (revisions **001–014**) |
| Dev DB | SQLite |
| Staging / prod DB | **PostgreSQL** |

Use the **existing codebase** — do not modify application functionality during provisioning.

---

## 3. Target architecture

```
UAT users
    │
 HTTPS
    │
 Staging URL (PUBLIC_APP_BASE_URL)
    │
 Frontend (static / CDN / app host)
    │
 VMS Backend API
    │
 PostgreSQL (application DB)
    │
 ┌─────────────────────────────────────┐
 │ External integrations (staging)    │
 │  • Microsoft Entra ID (auth)         │
 │  • Microsoft Graph (email)           │
 │  • ClamAV (file scan)                │
 └─────────────────────────────────────┘
```

**Disabled for initial RC** (must remain off):

- Physical access control (`ACCESS_CONTROL_ENABLED=false`)
- Badge printer (`BADGE_PRINTER_ENABLED=false`)
- Real AI (`AI_ENABLED=false`)

---

## 4. Staging URL

Provide an approved **HTTPS** hostname, e.g. `https://vms-uat.company-domain.com`.

Requirements:

- Valid TLS certificate
- No HTTP-only deployment
- Accessible to approved UAT users only (corporate access policy)
- Frontend and API routing configured (SPA + `/api/*` to backend)
- No uncontrolled public exposure

**Deliver:** `PUBLIC_APP_BASE_URL=https://…`

---

## 5. PostgreSQL — application database

Provision dedicated staging PostgreSQL for the **running application**.

| Requirement | Detail |
|-------------|--------|
| Version | Enterprise-supported PostgreSQL |
| TLS | **Required** (`DB_SSLMODE=require` or stronger) |
| Database | Dedicated VMS schema/database |
| User | Least-privilege application user (not superuser) |
| Storage | Encrypted at rest |
| Backups | Automated backups / PITR where platform supports |
| Timezone | UTC preferred |

**Deliver securely:** `DATABASE_URL`

Format:

```text
postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
```

---

## 6. PostgreSQL — integration test database (separate)

**Not** the application DB. Disposable DB for destructive automated tests.

| Variable | Purpose |
|----------|---------|
| `TEST_POSTGRES_URL` | e.g. `vms_staging_integration_test` |

Tests may: migrate, seed synthetic data, concurrency tests, reset data.

**Also set for test runner:**

```text
ALLOW_POSTGRES_TEST_DATABASE=true
ENABLE_LIVE_INTEGRATION_TESTS=true
```

---

## 7. PostgreSQL — restore test database (separate)

Third database for backup/restore rehearsal.

| Variable | Purpose |
|----------|---------|
| `TEST_POSTGRES_RESTORE_URL` | e.g. `vms_staging_restore_test` |

Flow: `TEST_POSTGRES_URL` → `pg_dump` → restore to `TEST_POSTGRES_RESTORE_URL` → validate. **Never restore over source.**

---

## 8. Database access & migrations

- Application user: only permissions required by VMS
- Migration user: elevated identity if needed for `alembic upgrade head`
- **Do not** grant superuser or access to unrelated databases

**Release migration procedure** (engineering executes):

1. DB reachable + backup/checkpoint  
2. `npm run migrate`  
3. Verify Alembic head (`014`)  
4. Start / update application  
5. Verify `/api/health/ready`

Do **not** auto-run migrations from every app instance at startup.

---

## 9. Microsoft Entra ID

**Authentication:** Entra → **Authorization:** VMS `AdminUser` + location scope (no JIT, no Entra group → VMS role mapping).

### SPA (frontend build-time)

```text
VITE_AUTH_MODE=entra
VITE_ENTRA_TENANT_ID=
VITE_ENTRA_CLIENT_ID=
VITE_ENTRA_API_SCOPE=
VITE_ENTRA_REDIRECT_URI=https://<staging>/auth/callback
VITE_ENTRA_POST_LOGOUT_URI=https://<staging>/login
VITE_API_BASE_URL=https://<staging>
VITE_ENABLE_SOURCEMAPS=false
```

Authorization Code + PKCE — **not** implicit grant.

### API (backend)

```text
AUTH_MODE=entra
ENTRA_TENANT_ID=
ENTRA_API_AUDIENCE=api://<API_APP_ID>
ENTRA_REQUIRED_SCOPE=VMS.Access
ENTRA_ALLOWED_CLIENT_IDS=          # optional allowlist
```

### Test personas (Entra accounts — VMS roles assigned inside app)

| # | Persona | Notes |
|---|---------|-------|
| 1 | GLOBAL_ADMIN | |
| 2 | HEAD_ADMIN | |
| 3 | SITE_ADMIN | e.g. Bangalore |
| 4 | SECURITY | e.g. Bangalore |
| 5 | Unknown user | Entra OK, **not** in VMS → `VMS_USER_NOT_AUTHORIZED` |
| 6 | Inactive user | Entra OK, inactive VMS mapping → `VMS_USER_INACTIVE` |

---

## 10. Microsoft Graph email

Required when `EMAIL_PROVIDER=ms_graph` (expected for staging RC).

```text
EMAIL_PROVIDER=ms_graph
GRAPH_TENANT_ID=
GRAPH_CLIENT_ID=
GRAPH_CLIENT_SECRET=              # or secret manager reference
GRAPH_SENDER_MAILBOX=             # dedicated staging sender
GRAPH_TIMEOUT_SECONDS=15
```

**Permission (app-only):** `Mail.Send` — do **not** grant Mail.Read, Directory.Read.All, etc. unless separately approved.

**Restrict** Graph app to approved sender mailbox where platform supports.

### Live test allowlist (engineering test runner only)

```text
EMAIL_LIVE_TEST_RECIPIENT=
LIVE_EMAIL_ALLOWED_RECIPIENTS=    # comma-separated approved UAT mailboxes
```

Templates validated: `HOST_APPROVAL_REQUEST`, `VISITOR_INVITATION`, `VISITOR_ARRIVED`, `UPCOMING_VISIT_REMINDER` (synthetic data only).

---

## 11. ClamAV

Required when `APP_ENV=production` (application rejects `dev_noop` scanner in production).

```text
FILE_SCANNER_PROVIDER=clamav
CLAMAV_HOST=
CLAMAV_PORT=3310
CLAMAV_TIMEOUT_SECONDS=15
```

- Backend must reach ClamAV on network (no public exposure)
- UAT: harmless PDF/JPG/PNG → CLEAN; EICAR standard test → rejected

---

## 12. Security keys (staging — production strength)

Deliver via **secret manager** / secure channel — **not** plain text in tickets or Git.

| Key | Notes |
|-----|-------|
| `AUDIT_INTEGRITY_KEY` | Min entropy; survives restarts |
| `DOCUMENT_ENCRYPTION_KEY` | Compliance file encryption |
| `VMS_DATA_ENCRYPTION_KEY` | Notification / token data at rest |

No weak values (`changeme`, `test`, `development`). Server-side only — never in frontend.

---

## 13. CORS

```text
CORS_ALLOWED_ORIGINS=https://<staging-hostname>
```

No wildcard `*`.

---

## 14. Full staging application configuration

```text
APP_ENV=production
APP_RELEASE_VERSION=1.0.0-rc1
AUTH_MODE=entra
DATABASE_URL=<staging PostgreSQL>
PUBLIC_APP_BASE_URL=https://<staging>
RATE_LIMIT_BACKEND=database
EMAIL_PROVIDER=ms_graph
FILE_SCANNER_PROVIDER=clamav
AI_ENABLED=false
AI_PROVIDER=disabled
ACCESS_CONTROL_ENABLED=false
ACCESS_CONTROL_PROVIDER=disabled
BADGE_PRINTER_ENABLED=false
BADGE_PRINTER_PROVIDER=disabled
log_format=json                    # maps to log_format in app if supported
LOG_LEVEL=INFO
DB_SSLMODE=require
DB_SQL_ECHO=false
SCHEMA_CHECK_ON_STARTUP=true
DEV_AUTH_ENABLED=false
ENABLE_LIVE_INTEGRATION_TESTS=false   # false on runtime; true only for test jobs
```

---

## 15. File storage

Persistent staging storage for encrypted compliance uploads (existing app abstraction under `data/uploads/` or equivalent mount).

- Not ephemeral container-only storage
- Restricted to backend
- Coordinated with DB backup/recovery

Do **not** change application storage architecture.

---

## 16. Logging

- `LOG_LEVEL=INFO`, structured logs preferred
- Logs must **not** contain: DB passwords, Graph secrets, Entra tokens, invitation/host approval tokens, encryption keys
- No SIEM required for this phase

---

## 17. Runtime instances

- **Minimum:** 1 backend instance  
- **Preferred for scheduler UAT:** 2 backend instances sharing same PostgreSQL (lease failover)

Schedulers: `notification-dispatch`, `upcoming-reminders`, `data-retention`, `physical-integrations` (if enabled).

---

## 18. Health endpoints

| Endpoint | Expected |
|----------|----------|
| `GET /api/health/live` | 200 when process alive |
| `GET /api/health/ready` | 200 when DB + schema + config ready; 503 when not |

---

## 19. Network

**Outbound from backend:**

- Microsoft Entra / Graph endpoints  
**Internal:**

- PostgreSQL  
- ClamAV  

No unnecessary inbound exposure.

---

## 20. UAT data & locations

- **No production visitor data**
- Synthetic data only
- Locations: **Bangalore**, **Mumbai**
- Visitor types: Business Visitor, Vendor, Contractor, Candidate, Delivery, VIP

---

## 21. Values to return (secure channel)

| Item | Variable / note |
|------|----------------|
| Staging URL | `PUBLIC_APP_BASE_URL` |
| App DB | `DATABASE_URL` |
| Integration test DB | `TEST_POSTGRES_URL` |
| Restore test DB | `TEST_POSTGRES_RESTORE_URL` |
| Entra tenant | `ENTRA_TENANT_ID`, `VITE_ENTRA_TENANT_ID` |
| Entra SPA client | `VITE_ENTRA_CLIENT_ID` |
| Entra API audience | `ENTRA_API_AUDIENCE` |
| Entra scope | `ENTRA_REQUIRED_SCOPE`, `VITE_ENTRA_API_SCOPE` |
| Redirect URIs | SPA callback / logout |
| Graph | tenant, client ID, secret **reference**, sender mailbox |
| Graph test recipients | `EMAIL_LIVE_TEST_RECIPIENT`, `LIVE_EMAIL_ALLOWED_RECIPIENTS` |
| ClamAV | host, port |
| Keys | secret **references** for audit / document / data encryption |
| CORS | `CORS_ALLOWED_ORIGINS` |
| Storage | persistent upload path / mount description |
| Backup | PITR / backup capability summary |

**Do not** send passwords or secrets in email, chat, Git, README, or frontend `.env`.

---

## 22. Staging acceptance checklist

Infrastructure provisioning is complete when:

- [ ] HTTPS staging URL works  
- [ ] `APP_ENV=production`  
- [ ] PostgreSQL application DB available  
- [ ] Separate integration-test DB available  
- [ ] Separate restore-test DB available  
- [ ] DB TLS enabled  
- [ ] Entra SSO staging app configured  
- [ ] Entra UAT test accounts available  
- [ ] Graph sender + test recipients (if email required)  
- [ ] ClamAV reachable  
- [ ] Production-strength staging encryption keys configured  
- [ ] Explicit CORS configured  
- [ ] `RATE_LIMIT_BACKEND=database`  
- [ ] `AI_ENABLED=false`  
- [ ] `ACCESS_CONTROL_ENABLED=false`  
- [ ] `BADGE_PRINTER_ENABLED=false`  
- [ ] Application starts  
- [ ] `/api/health/live` = 200  
- [ ] `/api/health/ready` = 200 after migrate + config  
- [ ] No mock/dev production providers enabled  

---

## 23. Engineering validation (after provisioning)

```bash
npm run migrate
npm run test:postgres
npm run pg:restore-rehearsal
npm run test:graph-live          # if Graph enabled
npm run test:clamav-live         # if ClamAV enabled
# Manual Entra browser UAT + docs/uat/final-uat-checklist.md
npm run production:check
npm run audit:seal && npm run audit:verify
npm run closure:matrix
```

---

## 24. Explicit exclusions

**Do not:**

- Deploy to production  
- Create production database or route production traffic  
- Migrate production data  
- Change production DNS  
- Enable physical access hardware or badge printers  
- Enable real AI  
- Modify VMS application code during provisioning  

---

## 25. Related documents

| Document | Purpose |
|----------|---------|
| [.env.staging.example](../../.env.staging.example) | Variable template (no secrets) |
| [staging-provisioning-report.md](./staging-provisioning-report.md) | DevOps completion report (template) |
| [final-uat-checklist.md](../uat/final-uat-checklist.md) | Operator UAT sign-off |
| [go-live-checklist.md](./go-live-checklist.md) | Pre-cutover checklist |
