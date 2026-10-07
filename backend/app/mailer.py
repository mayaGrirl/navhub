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


def _text(stored: str, fallback: str) -> str:
    value = (stored or "").strip()
    return value or (fallback or "")


def _port(stored: int, fallback: int) -> int:
    return int(stored or 0) or int(fallback or 465)


def gmail_account(row: MailSetting) -> dict:
    return {
        "host": _text(row.gmail_host, settings.mail_smtp_host),
        "port": _port(row.gmail_port, settings.mail_smtp_port),
        "user": _text(row.gmail_user, settings.mail_smtp_user),
        "password": _text(row.gmail_pass, settings.mail_smtp_pass),
        "sender": _text(row.gmail_from, settings.mail_from_address or settings.mail_from),
        "name": _text(row.gmail_from_name, settings.mail_from_name),
    }


def netease_account(row: MailSetting) -> dict:
    gmail = gmail_account(row)
    return {
        "host": _text(row.netease_host, settings.mail_smtp_163_host),
        "port": _port(row.netease_port, settings.mail_smtp_163_port),
        "user": _text(row.netease_user, settings.mail_smtp_163_user),
        "password": _text(row.netease_pass, settings.mail_smtp_163_pass),
        "sender": _text(row.netease_from, settings.mail_smtp_163_from or gmail["sender"]),
        "name": _text(row.netease_from_name, settings.mail_smtp_163_from_name or gmail["name"]),
    }


def sendgrid_account(row: MailSetting) -> dict:
    gmail = gmail_account(row)
    return {
        "key": _text(row.sendgrid_key, settings.sendgrid_api_key),
        "sender": _text(row.sendgrid_from, gmail["sender"]),
        "name": _text(row.sendgrid_from_name, gmail["name"]),
    }


def mailgun_account(row: MailSetting) -> dict:
    gmail = gmail_account(row)
    return {
        "key": _text(row.mailgun_key, settings.mailgun_api_key),
        "domain": _text(row.mailgun_domain, settings.mailgun_domain),
        "region": _text(row.mailgun_region, settings.mailgun_region) or "us",
        "sender": _text(row.mailgun_from, gmail["sender"]),
        "name": _text(row.mailgun_from_name, gmail["name"]),
    }


def public_mail(row: MailSetting) -> dict:
    gmail = gmail_account(row)
    netease = netease_account(row)
    sendgrid = sendgrid_account(row)
    mailgun = mailgun_account(row)
    return {
        "provider": settings.mail_provider,
        "from_name": gmail["name"],
        "from_address": gmail["sender"],
        "gmail_enabled": row.gmail_enabled,
        "gmail_ready": bool(gmail["user"] and gmail["password"]),
        "gmail_host": gmail["host"],
        "gmail_port": gmail["port"],
        "gmail_user": gmail["user"],
        "gmail_pass": gmail["password"],
        "gmail_from": gmail["sender"],
        "gmail_from_name": gmail["name"],
        "netease_enabled": row.netease_enabled,
        "netease_ready": bool(netease["user"] and netease["password"]),
        "netease_host": netease["host"],
        "netease_port": netease["port"],
        "netease_user": netease["user"],
        "netease_pass": netease["password"],
        "netease_from": netease["sender"],
        "netease_from_name": netease["name"],
        "sendgrid_enabled": row.sendgrid_enabled,
        "sendgrid_key": sendgrid["key"],
        "sendgrid_from": sendgrid["sender"],
        "sendgrid_from_name": sendgrid["name"],
        "mailgun_enabled": row.mailgun_enabled,
        "mailgun_key": mailgun["key"],
        "mailgun_domain": mailgun["domain"],
        "mailgun_region": mailgun["region"],
        "mailgun_from": mailgun["sender"],
        "mailgun_from_name": mailgun["name"],
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
    gmail = gmail_account(row)
    netease = netease_account(row)
    if row.gmail_enabled and gmail["user"] and gmail["password"]:
        order.append("gmail")
    if row.netease_enabled and netease["user"] and netease["password"]:
        order.append("163")
    sendgrid = sendgrid_account(row)
    mailgun = mailgun_account(row)
    if row.sendgrid_enabled and sendgrid["key"]:
        order.append("sendgrid")
    if row.mailgun_enabled and mailgun["key"] and mailgun["domain"]:
        order.append("mailgun")
    if row.ses_enabled and settings.aws_ses_key and settings.aws_ses_secret:
        order.append("ses")
    return order or ["log"]


def _send_one(row: MailSetting, channel: str, recipient: str, subject: str, body: str) -> None:
    gmail = gmail_account(row)
    netease = netease_account(row)
    sender = gmail["sender"]
    if channel == "gmail":
        _smtp(gmail["host"], gmail["port"], gmail["user"], gmail["password"], gmail["sender"], gmail["name"], recipient, subject, body)
    elif channel == "163":
        _smtp(netease["host"], netease["port"], netease["user"], netease["password"], netease["sender"], netease["name"], recipient, subject, body)
    elif channel == "sendgrid":
        sendgrid = sendgrid_account(row)
        response = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {sendgrid['key']}"},
            json={"personalizations": [{"to": [{"email": recipient}]}], "from": {"email": sendgrid["sender"], "name": sendgrid["name"]}, "subject": subject, "content": [{"type": "text/plain", "value": body}]},
            timeout=settings.mail_smtp_timeout,
        )
        response.raise_for_status()
    elif channel == "mailgun":
        mailgun = mailgun_account(row)
        host = "api.eu.mailgun.net" if mailgun["region"] == "eu" else "api.mailgun.net"
        response = httpx.post(
            f"https://{host}/v3/{mailgun['domain']}/messages",
            auth=("api", mailgun["key"]),
            data={"from": f"{mailgun['name']} <{mailgun['sender']}>", "to": recipient, "subject": subject, "text": body},
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
            _send_one(row, channel, recipient, subject, body)
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
