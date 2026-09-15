# Post-Deploy Smoke Checklist

Run within 30 minutes of production cutover. Not a full UAT repeat.

1. [ ] `GET /api/health/live` → 200, version present
2. [ ] `GET /api/health/ready` → 200 READY (or documented expected state)
3. [ ] Global Admin Entra login → `/api/me` correct role
4. [ ] Operations readiness page loads (Global Admin)
5. [ ] Public visitor registration page loads (Bangalore token URL)
6. [ ] Self-registration submit succeeds (synthetic visitor)
7. [ ] Expected Today lists new registration (staff)
8. [ ] Check-in smoke on pre-staged APPROVED visit (if available)
9. [ ] Onsite list reflects check-in
10. [ ] Checkout smoke on same visit
11. [ ] `npm run audit:verify` → VALID (from ops workstation)
12. [ ] Graph test notification delivered (if email critical path)
13. [ ] No elevated 5xx in application logs
14. [ ] Scheduler lease owner visible on operations readiness
15. [ ] Rollback decision documented if any check fails
