# Provider Outage Runbook

## Microsoft Graph email

- Check operations readiness / security readiness email status
- Inspect notification queue (pending/failed counts)
- Use safe retry actions on notification operations pages
- Do not manually recreate duplicate visitor invitations

## ClamAV

- File uploads may queue or fail per existing scanner semantics
- Readiness reflects scanner state

## Access control provider

- Provisioning/revocation queues may backlog
- CHECKED_OUT + ACTIVE access → highest attention
- Revocation pending → high attention
- Provision failure → reception manual fallback

## Badge printer provider

- Print jobs queue; failed jobs visible on access operations and readiness pages
- Use safe retry on operational pages

Preserve existing VMS fallback semantics; disable integrations only via configuration when approved.
