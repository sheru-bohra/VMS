"""Lightweight email templates for notification rendering."""

from __future__ import annotations

import html
from typing import Any, Dict


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def render_host_approval_request(payload: Dict[str, Any]) -> tuple[str, str]:
    visitor_name = _esc(payload.get("visitor_name", "Visitor"))
    subject = f"Visitor approval required — {visitor_name}"
    walk_in = payload.get("is_walk_in", True)
    waiting_line = (
        "The visitor is currently waiting at reception.\n"
        if walk_in
        else f"Scheduled for {_esc(payload.get('scheduled_display', 'the scheduled time'))}.\n"
    )
    body = (
        "A visitor has requested to meet you.\n\n"
        f"Visitor\n{visitor_name}\n\n"
        f"Company\n{_esc(payload.get('company', '—'))}\n\n"
        f"Location\n{_esc(payload.get('site_name', '—'))}\n\n"
        f"Purpose\n{_esc(payload.get('purpose', '—'))}\n\n"
        f"{waiting_line}\n"
        "Please review the visitor request using the secure link provided."
    )
    return subject, body


def render_host_approval_request_html(payload: Dict[str, Any]) -> str:
    url = payload.get("approval_url")
    link = f'<p><a href="{_esc(url)}">Review Visitor Request</a></p>' if url else ""
    visitor_name = _esc(payload.get("visitor_name", "Visitor"))
    return (
        f"<p>A visitor has requested to meet you.</p>"
        f"<p><strong>Visitor:</strong> {visitor_name}<br/>"
        f"<strong>Company:</strong> {_esc(payload.get('company', '—'))}<br/>"
        f"<strong>Location:</strong> {_esc(payload.get('site_name', '—'))}<br/>"
        f"<strong>Purpose:</strong> {_esc(payload.get('purpose', '—'))}</p>"
        f"{link}"
    )


def render_visitor_arrived(payload: Dict[str, Any]) -> tuple[str, str]:
    visitor_name = _esc(payload.get("visitor_name", "Visitor"))
    subject = f"Your visitor has arrived — {visitor_name}"
    body = (
        f"{visitor_name} from {_esc(payload.get('company', '—'))} has checked in at {_esc(payload.get('site_name', '—'))}.\n\n"
        f"Visit\n{_esc(payload.get('purpose', '—'))}\n\n"
        f"Checked in\n{_esc(payload.get('checked_in_display', '—'))}\n\n"
        "The visitor is now onsite."
    )
    return subject, body


def render_visitor_arrived_html(payload: Dict[str, Any]) -> str:
    visitor_name = _esc(payload.get("visitor_name", "Visitor"))
    return (
        f"<p>{visitor_name} from {_esc(payload.get('company', '—'))} has checked in at "
        f"{_esc(payload.get('site_name', '—'))}.</p>"
        f"<p><strong>Purpose:</strong> {_esc(payload.get('purpose', '—'))}<br/>"
        f"<strong>Checked in:</strong> {_esc(payload.get('checked_in_display', '—'))}</p>"
    )


def render_upcoming_reminder(payload: Dict[str, Any]) -> tuple[str, str]:
    visitor_name = _esc(payload.get("visitor_name", "Visitor"))
    subject = f"Visitor arriving soon — {visitor_name}"
    body = (
        "Your visitor is expected soon.\n\n"
        f"{visitor_name}\n"
        f"{_esc(payload.get('company', '—'))}\n\n"
        f"{_esc(payload.get('site_name', '—'))}\n"
        f"{_esc(payload.get('scheduled_display', '—'))}\n\n"
        f"Purpose\n{_esc(payload.get('purpose', '—'))}"
    )
    return subject, body


def render_upcoming_reminder_html(payload: Dict[str, Any]) -> str:
    visitor_name = _esc(payload.get("visitor_name", "Visitor"))
    return (
        f"<p>Your visitor is expected soon.</p>"
        f"<p>{visitor_name}<br/>{_esc(payload.get('company', '—'))}<br/>"
        f"{_esc(payload.get('site_name', '—'))}<br/>{_esc(payload.get('scheduled_display', '—'))}</p>"
        f"<p><strong>Purpose:</strong> {_esc(payload.get('purpose', '—'))}</p>"
    )


def render_visitor_invitation(payload: Dict[str, Any]) -> tuple[str, str]:
    site = _esc(payload.get("site_name", "Office"))
    visitor_name = _esc(payload.get("visitor_name", "Visitor"))
    subject = f"Your visit is approved — {site}"
    body = (
        f"Dear {visitor_name},\n\n"
        f"Your visit to {site} is approved.\n\n"
        f"Host: {_esc(payload.get('host_name', '—'))}\n"
        f"When: {_esc(payload.get('scheduled_display', '—'))}\n"
        f"Reference: {_esc(payload.get('registration_reference', '—'))}\n\n"
        f"Open your visitor invitation: {_esc(payload.get('invitation_url', ''))}\n\n"
        "Please bring valid ID and arrive during your scheduled time."
    )
    return subject, body


def render_visitor_invitation_html(payload: Dict[str, Any]) -> str:
    visitor_name = _esc(payload.get("visitor_name", "Visitor"))
    url = payload.get("invitation_url")
    link = f'<p><a href="{_esc(url)}">Open Visitor Invitation</a></p>' if url else ""
    qr = '<p><img src="cid:visitor_qr" alt="Visitor QR"/></p>' if payload.get("qr_png_base64") else ""
    return (
        f"<p>Dear {visitor_name},</p>"
        f"<p>Your visit to {_esc(payload.get('site_name', '—'))} is approved.</p>"
        f"<p><strong>Host:</strong> {_esc(payload.get('host_name', '—'))}<br/>"
        f"<strong>When:</strong> {_esc(payload.get('scheduled_display', '—'))}<br/>"
        f"<strong>Reference:</strong> {_esc(payload.get('registration_reference', '—'))}</p>"
        f"{qr}{link}"
    )


TEMPLATE_RENDERERS = {
    "host_approval_request": render_host_approval_request,
    "visitor_arrived": render_visitor_arrived,
    "upcoming_visit_reminder": render_upcoming_reminder,
    "visitor_invitation": render_visitor_invitation,
}

TEMPLATE_HTML_RENDERERS = {
    "host_approval_request": render_host_approval_request_html,
    "visitor_arrived": render_visitor_arrived_html,
    "upcoming_visit_reminder": render_upcoming_reminder_html,
    "visitor_invitation": render_visitor_invitation_html,
}
