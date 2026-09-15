# Final UAT Checklist

Record each item as **PASS**, **FAIL**, **BLOCKED**, or **NOT_APPLICABLE**. Do not pre-fill PASS without evidence.

## Phase 16.3 status (2026-08-27)

**STAGING VALIDATION BLOCKED — APPROVED STAGING INFRASTRUCTURE NOT AVAILABLE.**

| Detected config | Value |
|-----------------|-------|
| `APP_ENV` | `development` (required: `production`) |
| Database | SQLite (required: staging PostgreSQL) |
| `AUTH_MODE` | `dev` (required: `entra`) |
| `RATE_LIMIT_BACKEND` | `memory` (required: `database`) |
| `TEST_POSTGRES_URL` | not set |

No live validation performed. Production remains **NO_GO**.

## Phase 16.2 status (2026-08-27)

| Item | Status |
|------|--------|
| Automated regression (271 backend / 54 frontend / 26 release) | PASS |
| Staging environment connected | **NO** — local SQLite/dev auth only |
| Live PostgreSQL | **NOT PERFORMED** |
| Backup/restore rehearsal | **NOT PERFORMED** |
| Live Entra SSO | **NOT PERFORMED** |
| Live Graph email | **NOT PERFORMED** |
| Live ClamAV | **NOT PERFORMED** |
| Manual browser UAT (sections below) | **NOT PERFORMED** |

Production go-live remains **NO_GO**.

## Phase 16.1 status (2026-08-27)

| Item | Status |
|------|--------|
| Automated regression (271 backend / 54 frontend / 22 release) | PASS |
| Manual browser UAT (sections below) | **NOT PERFORMED** — operator sign-off required |
| Live PostgreSQL | **NOT PERFORMED** — no `TEST_POSTGRES_URL` |
| Live Entra SSO | **NOT PERFORMED** — no approved tenant/browser session |
| Live Graph email | **NOT PERFORMED** — not configured |
| Live ClamAV | **NOT PERFORMED** — not configured |
| Backup/restore rehearsal | **NOT PERFORMED** |

Production go-live remains **NO_GO** until manual UAT and required live validations complete.

## Personas

- [ ] Global Admin — full authorized scope
- [ ] Head Admin — management scope, read-only operations readiness
- [ ] Bangalore Site Admin — BLR only
- [ ] Bangalore Security — BLR security operations
- [ ] Host (synthetic / approved test account)
- [ ] Visitor (public flows)

## Core workflows

- [ ] Walk-in registration → host approval → security → check-in → badge → checkout
- [ ] Advance invitation → approval → visitor invitation → QR → arrival → check-in → checkout
- [ ] Host approval via secure link
- [ ] Rejected visitor cannot check in
- [ ] Expired invitation cannot check in
- [ ] Vendor / contractor with compliance verification
- [ ] Non-compliant vendor blocked at check-in
- [ ] Returning contractor reuses valid documents
- [ ] Watchlist BLOCK prevents approval/check-in
- [ ] Watchlist REVIEW requires security review
- [ ] Emergency roll-call lifecycle
- [ ] Reports dashboard + CSV + XLSX (Global/Head Admin)
- [ ] Retention preview + execute on synthetic old data
- [ ] Physical access mock (if enabled): provision on check-in, revoke on checkout
- [ ] Badge printer mock (if enabled): print + reprint

## Authorization

- [ ] Site Admin denied Mumbai data (API + UI)
- [ ] Security denied reports and management analytics
- [ ] AI Copilot scope denial for Site Admin management queries
- [ ] Unauthenticated staff APIs denied

## Security smoke

- [ ] Token expiry / replay (host approval, invitation)
- [ ] XSS payloads escaped in UI/email/export
- [ ] CSV/XLSX formula injection sanitized
- [ ] File upload security (traversal, size, unauthorized download)
- [ ] CORS / CSP / security headers
- [ ] Open redirect regression on login return URL

## Live integrations (only when configured)

- [ ] Microsoft Entra SSO (browser UAT)
- [ ] Microsoft Graph test email to approved recipient
- [ ] ClamAV clean file + EICAR
- [ ] PostgreSQL live suite (`npm run test:postgres`)

## Post-UAT gates

- [ ] `npm run audit:verify` → VALID
- [ ] No secrets in logs or built frontend assets
