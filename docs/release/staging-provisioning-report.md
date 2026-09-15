# Staging Provisioning Report (DevOps — complete and return)

**Application:** PayU VMS  
**Release:** `1.0.0-rc1`  
**Environment:** Staging / UAT only  
**Report date:** _YYYY-MM-DD_  
**Prepared by:** _name / team_

Do **not** include passwords, client secrets, or encryption keys in this document. Use secret manager references only.

---

## Summary

| # | Item | Status |
|---|------|--------|
| 1 | Staging URL (`PUBLIC_APP_BASE_URL`) | _pending / provided via secure channel_ |
| 2 | PostgreSQL version | _e.g. 15.x_ |
| 3 | Application DB ready | _yes / no_ |
| 4 | Integration-test DB ready (`TEST_POSTGRES_URL`) | _yes / no_ |
| 5 | Restore-test DB ready (`TEST_POSTGRES_RESTORE_URL`) | _yes / no_ |
| 6 | TLS enabled (`DB_SSLMODE`) | _yes / no_ |
| 7 | Entra configured | _yes / no_ |
| 8 | Entra test personas ready | _yes / no_ |
| 9 | Graph configured | _yes / no / not required_ |
| 10 | Graph sender mailbox | _address_ |
| 11 | Graph test recipients approved | _yes / no_ |
| 12 | ClamAV configured | _yes / no_ |
| 13 | Secret references configured (audit / encryption keys) | _yes / no_ |
| 14 | Rate limit backend | _database / other_ |
| 15 | AI | _disabled / enabled_ |
| 16 | Access Control | _disabled / enabled_ |
| 17 | Badge Printer | _disabled / enabled_ |
| 18 | Staging persistent storage ready | _yes / no — describe mount/path_ |
| 19 | Backup / PITR capability | _yes / no — describe_ |
| 20 | `/api/health/live` | _200 / other_ |
| 21 | `/api/health/ready` | _200 / 503 — note if migrations pending_ |
| 22 | Known infrastructure blockers | _list or none_ |
| 23 | Production deployment performed | **must be NO** |

---

## Staging acceptance checklist

Copy from [staging-provisioning-request.md](./staging-provisioning-request.md) §22 and mark each item when complete.

---

## Secure delivery confirmation

- [ ] `DATABASE_URL` delivered via approved secret channel  
- [ ] `TEST_POSTGRES_URL` delivered via approved secret channel  
- [ ] `TEST_POSTGRES_RESTORE_URL` delivered via approved secret channel  
- [ ] Graph credentials delivered via approved secret channel  
- [ ] Encryption keys delivered via approved secret channel  
- [ ] No secrets committed to Git or broad-audience tickets  

---

## Handoff to engineering

When all blocking items are complete, notify VMS engineering to execute **Phase 16.3** staging validation per `docs/release/staging-provisioning-request.md` §23.

**Production go-live remains NO_GO until engineering validation completes.**
