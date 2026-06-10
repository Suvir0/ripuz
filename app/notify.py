"""
Fire-and-forget webhook notifications when jobs finish.

Supports Discord (reads "content") and Slack / ntfy (reads "text").
Failures are logged and silently ignored — notifications must never break jobs.
"""
import logging

import httpx

from app.settings_store import get_notify_webhook_url

logger = logging.getLogger(__name__)

_USER_AGENT = "ripuz/1.0 (https://github.com/Suvir0/ripuz)"


def notify_job_finished(job: dict) -> None:
    """POST a notification to the configured webhook URL (if any)."""
    url = get_notify_webhook_url()
    if not url:
        return
    job_id = job.get("id", "?")
    job_type = job.get("type", "?")
    status = job.get("status", "?")
    msg = f"Ripuz: job #{job_id} ({job_type}) finished — {status}"
    try:
        with httpx.Client(timeout=10) as client:
            client.post(
                url,
                json={"content": msg, "text": msg},
                headers={"User-Agent": _USER_AGENT},
            )
    except Exception as exc:
        logger.debug("webhook notify failed: %s", exc)
