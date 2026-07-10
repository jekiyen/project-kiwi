"""Message formatting — turns a NotificationEvent into provider-agnostic text.

Output uses a small set of Telegram-HTML tags (<b>, <a>). Providers that
don't support HTML should strip tags before sending.
"""
import html
from typing import Any

from backend.notifications.base import NotificationEvent, NotificationEventType

BRAND = "🥝 <b>Kiwi</b>"


def _esc(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def _high_score_job(data: dict) -> str:
    title = _esc(data.get("title", "Unknown role"))
    employer = _esc(data.get("employer", ""))
    location = _esc(data.get("location", ""))
    score = data.get("score", 0)
    reasons = [str(r) for r in data.get("reasons", [])][:3] or ["Strong overall match"]
    reason_lines = "\n".join(f"• {_esc(r)}" for r in reasons)

    lines = [BRAND, "", "<b>New High Match Job</b>", "", title]
    subtitle = " · ".join(x for x in [employer, location] if x)
    if subtitle:
        lines.append(subtitle)
    lines.append(f"Score: {score}/100")
    lines.append("")
    lines.append("<b>Top reasons</b>")
    lines.append(reason_lines)
    if data.get("url"):
        lines.append("")
        lines.append(f'<a href="{html.escape(str(data["url"]))}">View listing</a>')
    return "\n".join(lines)


def _scan_completed(data: dict) -> str:
    return "\n".join([
        BRAND,
        "",
        "<b>Scan Completed</b>",
        "",
        f"{data.get('jobs_found', 0)} scanned",
        f"{data.get('new_jobs', 0)} new jobs",
        f"{data.get('high_priority', 0)} high priority",
    ])


def _scan_failed(data: dict) -> str:
    lines = [
        BRAND,
        "",
        "⚠️ <b>Scan Failed</b>",
        "",
        f"{data.get('failed_count', 0)} of {data.get('total_scrapers', 0)} source(s) failed",
    ]
    for err in [str(e) for e in data.get("errors", [])][:3]:
        lines.append(f"• {_esc(err)}")
    return "\n".join(lines)


def _application_created(data: dict) -> str:
    title = _esc(data.get("title", "Unknown role"))
    employer = _esc(data.get("employer", ""))
    status = _esc(str(data.get("status", "saved")).title())
    lines = [BRAND, "", "<b>Application Saved</b>", "", title]
    if employer:
        lines.append(employer)
    lines.append(f"Status: {status}")
    return "\n".join(lines)


def _application_status_changed(data: dict) -> str:
    title = _esc(data.get("title", "Unknown role"))
    employer = _esc(data.get("employer", ""))
    from_status = _esc(str(data.get("from_status", "—")).title())
    to_status = _esc(str(data.get("to_status", "—")).title())
    heading = f"{title} — {employer}" if employer else title
    return "\n".join([
        BRAND,
        "",
        "<b>Application Updated</b>",
        "",
        heading,
        f"{from_status} → {to_status}",
    ])


def _test(_data: dict) -> str:
    return "\n".join([
        BRAND,
        "",
        "<b>Test Notification</b>",
        "",
        "If you can read this, notifications are working correctly.",
    ])


_FORMATTERS = {
    NotificationEventType.HIGH_SCORE_JOB: _high_score_job,
    NotificationEventType.SCAN_COMPLETED: _scan_completed,
    NotificationEventType.SCAN_FAILED: _scan_failed,
    NotificationEventType.APPLICATION_CREATED: _application_created,
    NotificationEventType.APPLICATION_STATUS_CHANGED: _application_status_changed,
    NotificationEventType.TEST: _test,
}


def format_message(event: NotificationEvent) -> str:
    formatter = _FORMATTERS.get(event.type)
    if formatter is None:
        return f"{BRAND}\n\n{event.type.value}"
    return formatter(event.data)
