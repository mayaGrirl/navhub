import smtplib
import ssl
import threading
import time
from datetime import datetime, timedelta
from email.message import EmailMessage

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import MailLog, MailSetting, MailTask, User


def mail_row(db) -> MailSetting:
    row = db.get(MailSetting, 1)
    if not row:
        row = MailSetting(
            id=1,
            gmail_enabled=False,
            netease_enabled=False,
            notify_default=settings.notify_mail_default,
            money_dm=settings.mail_money_dm,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def public_mail(row: MailSetting) -> dict:
    return {
        "provider": settings.mail_provider,
        "from_name": settings.mail_from_name,
        "from_address": settings.mail_from_address or settings.mail_from,
        "gmail_enabled": row.gmail_enabled,
        "gmail_ready": bool(settings.mail_smtp_user and settings.mail_smtp_pass),
        "netease_enabled": row.netease_enabled,
        "netease_ready": bool(settings.mail_smtp_163_user and settings.mail_smtp_163_pass),
        "sendgrid_enabled": row.sendgrid_enabled,
        "sendgrid_ready": bool(settings.sendgrid_api_key),
        "mailgun_enabled": row.mailgun_enabled,
        "mailgun_ready": bool(settings.mailgun_api_key and settings.mailgun_domain),
        "ses_enabled": row.ses_enabled,
        "ses_ready": bool(settings.aws_ses_key and settings.aws_ses_secret),
        "fallback": settings.mail_smtp_fallback,
        "notify_default": row.notify_default,
        "money_dm": row.money_dm,
    }


def _log(db, recipient: str, subject: str, channel: str, status: str, message: str) -> None:
    db.add(MailLog(recipient=recipient[:200], subject=subject[:200], channel=channel, status=status, message=message[:500]))
    db.commit()


def _smtp(host: str, port: int, user: str, password: str, sender: str, name: str, recipient: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = f"{name} <{sender}>" if name else sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)
    context = ssl.create_default_context() if settings.mail_smtp_verify_peer else ssl._create_unverified_context()
    with smtplib.SMTP_SSL(host, port, timeout=settings.mail_smtp_timeout, context=context) as client:
        client.login(user, password)
        client.send_message(msg)


def _channels(row: MailSetting) -> list[str]:
    order = []
    if row.gmail_enabled and settings.mail_smtp_user and settings.mail_smtp_pass:
        order.append("gmail")
    if row.netease_enabled and settings.mail_smtp_163_user and settings.mail_smtp_163_pass:
        order.append("163")
    if row.sendgrid_enabled and settings.sendgrid_api_key:
        order.append("sendgrid")
    if row.mailgun_enabled and settings.mailgun_api_key and settings.mailgun_domain:
        order.append("mailgun")
    if row.ses_enabled and settings.aws_ses_key and settings.aws_ses_secret:
        order.append("ses")
    return order or ["log"]


def _send_one(channel: str, recipient: str, subject: str, body: str) -> None:
    sender = settings.mail_from_address or settings.mail_from
    if channel == "gmail":
        _smtp(settings.mail_smtp_host, settings.mail_smtp_port, settings.mail_smtp_user, settings.mail_smtp_pass, sender, settings.mail_from_name, recipient, subject, body)
    elif channel == "163":
        _smtp(settings.mail_smtp_163_host, settings.mail_smtp_163_port, settings.mail_smtp_163_user, settings.mail_smtp_163_pass, settings.mail_smtp_163_from or sender, settings.mail_smtp_163_from_name or settings.mail_from_name, recipient, subject, body)
    elif channel == "sendgrid":
        response = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            json={"personalizations": [{"to": [{"email": recipient}]}], "from": {"email": sender, "name": settings.mail_from_name}, "subject": subject, "content": [{"type": "text/plain", "value": body}]},
            timeout=settings.mail_smtp_timeout,
        )
        response.raise_for_status()
    elif channel == "mailgun":
        host = "api.eu.mailgun.net" if settings.mailgun_region == "eu" else "api.mailgun.net"
        response = httpx.post(
            f"https://{host}/v3/{settings.mailgun_domain}/messages",
            auth=("api", settings.mailgun_api_key),
            data={"from": f"{settings.mail_from_name} <{sender}>", "to": recipient, "subject": subject, "text": body},
            timeout=settings.mail_smtp_timeout,
        )
        response.raise_for_status()
    elif channel == "ses":
        raise RuntimeError("SES 需要单独配置发信域名后再开启")
    else:
        return


def deliver(db, recipient: str, subject: str, body: str) -> str:
    row = mail_row(db)
    last = "已记录，未真正发出"
    for channel in _channels(row):
        try:
            _send_one(channel, recipient, subject, body)
            _log(db, recipient, subject, channel, "sent" if channel != "log" else "logged", "" if channel != "log" else last)
            return channel
        except Exception as exc:
            last = str(exc)[:500]
            _log(db, recipient, subject, channel, "error", last)
            if not settings.mail_smtp_fallback:
                break
    return "error"


def audience_users(db, audience: str) -> list[User]:
    rows = db.scalars(select(User).where(User.role != "admin", User.banned.is_(False))).all()
    if audience == "vip":
        return [row for row in rows if row.plan == "vip"]
    if audience == "free":
        return [row for row in rows if row.plan != "vip"]
    return list(rows)


def send_bulk(subject: str, body: str, audience: str) -> dict:
    db = SessionLocal()
    try:
        users = audience_users(db, audience)
        sent = 0
        for user in users:
            if user.email:
                deliver(db, user.email, subject, body)
                sent += 1
        return {"sent": sent}
    finally:
        db.close()


def schedule_mail() -> None:
    def loop():
        while True:
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                tasks = db.scalars(select(MailTask).where(MailTask.enabled.is_(True))).all()
                due = []
                for task in tasks:
                    ready = task.run_at and task.run_at <= now
                    if not ready:
                        continue
                    if task.last_run_at and not task.interval_minutes:
                        continue
                    if task.last_run_at and task.interval_minutes and task.last_run_at > now - timedelta(minutes=task.interval_minutes):
                        continue
                    due.append((task.id, task.subject, task.body, task.audience, task.interval_minutes))
                for task_id, subject, body, audience, interval in due:
                    send_bulk(subject, body, audience)
                    task = db.get(MailTask, task_id)
                    if task:
                        task.last_run_at = datetime.utcnow()
                        if not interval:
                            task.enabled = False
                        else:
                            task.run_at = datetime.utcnow() + timedelta(minutes=interval)
                        db.commit()
            except Exception:
                pass
            finally:
                db.close()
            time.sleep(60)

    threading.Thread(target=loop, daemon=True).start()
