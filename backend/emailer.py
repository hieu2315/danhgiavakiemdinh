"""SMTP adapter for ReLoop's notification outbox. Delivery is opt-in via environment."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr


def configured() -> bool:
    return bool(os.environ.get("RELOOP_SMTP_HOST") and os.environ.get("RELOOP_EMAIL_FROM"))


def send(to_address: str, subject: str, body: str) -> None:
    host = os.environ["RELOOP_SMTP_HOST"]
    port = int(os.environ.get("RELOOP_SMTP_PORT", "587"))
    sender = os.environ["RELOOP_EMAIL_FROM"]
    message = EmailMessage()
    message["From"] = formataddr((os.environ.get("RELOOP_EMAIL_NAME", "ReLoop Market"), sender))
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    username = os.environ.get("RELOOP_SMTP_USER")
    password = os.environ.get("RELOOP_SMTP_PASSWORD")
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=12) as smtp:
            if username:
                smtp.login(username, password or "")
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=12) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            if username:
                smtp.login(username, password or "")
            smtp.send_message(message)
