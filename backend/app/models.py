from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80), default="")
    proxy_token: Mapped[str] = mapped_column(String(80), default="")
    proxy_unlimited: Mapped[bool] = mapped_column(Boolean, default=False)
    proxy_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    plan: Mapped[str] = mapped_column(String(20), default="free")
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    totp_secret: Mapped[str] = mapped_column(String(64), default="")
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    points: Mapped[int] = mapped_column(Integer, default=0)
    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    last_ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuthLog(Base):
    __tablename__ = "auth_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="login")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default="")
    action: Mapped[str] = mapped_column(String(40), default="")
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    detail: Mapped[str] = mapped_column(String(800), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Tab(Base):
    __tablename__ = "tabs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title_en: Mapped[str] = mapped_column(String(120))
    title_zh: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="links")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    adult: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_crawl: Mapped[bool] = mapped_column(Boolean, default=False)
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    categories: Mapped[list["Category"]] = relationship(back_populates="tab", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tab_id: Mapped[int] = mapped_column(ForeignKey("tabs.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(80))
    title_en: Mapped[str] = mapped_column(String(120))
    title_zh: Mapped[str] = mapped_column(String(120))
    sort: Mapped[int] = mapped_column(Integer, default=0)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    tab: Mapped[Tab] = relationship(back_populates="categories")
    links: Mapped[list["Link"]] = relationship(back_populates="category", cascade="all, delete-orphan")


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    title_en: Mapped[str] = mapped_column(String(160))
    title_zh: Mapped[str] = mapped_column(String(160))
    description_en: Mapped[str] = mapped_column(Text, default="")
    description_zh: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(500))
    norm_url: Mapped[str] = mapped_column(String(500), default="", index=True)
    logo_url: Mapped[str] = mapped_column(String(500), default="")
    attachment_url: Mapped[str] = mapped_column(String(500), default="")
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hot: Mapped[bool] = mapped_column(Boolean, default=False)
    vip_badge: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="published")
    source: Mapped[str] = mapped_column(String(20), default="admin")
    review_note: Mapped[str] = mapped_column(String(200), default="")
    client_ip: Mapped[str] = mapped_column(String(64), default="")
    points_awarded: Mapped[bool] = mapped_column(Boolean, default=False)
    submitter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0)
    recommend_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    counts_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    clicks_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    category: Mapped[Category] = relationship(back_populates="links")


class Level(Base):
    __tablename__ = "levels"

    level: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    min_points: Mapped[int] = mapped_column(Integer, default=0)
    proxy_per_minute: Mapped[int] = mapped_column(Integer, default=10)


class PointRule(Base):
    __tablename__ = "point_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    points_per_link: Mapped[int] = mapped_column(Integer, default=1)


class AdminAlert(Base):
    __tablename__ = "admin_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(String(300), default="")
    handled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IpBan(Base):
    __tablename__ = "ip_bans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(String(64), unique=True)
    reason: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LinkMark(Base):
    __tablename__ = "link_marks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))


class Ad(Base):
    __tablename__ = "ads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[str] = mapped_column(String(40), default="inline")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    link_url: Mapped[str] = mapped_column(String(500), default="")
    title_en: Mapped[str] = mapped_column(String(160), default="")
    title_zh: Mapped[str] = mapped_column(String(160), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    show_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    title_en: Mapped[str] = mapped_column(String(160), default="")
    title_zh: Mapped[str] = mapped_column(String(160), default="")
    body_en: Mapped[str] = mapped_column(Text, default="")
    body_zh: Mapped[str] = mapped_column(Text, default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(80), default="")
    im: Mapped[str] = mapped_column(String(160), default="")
    address: Mapped[str] = mapped_column(String(255), default="")


class GithubRank(Base):
    __tablename__ = "github_ranks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period: Mapped[str] = mapped_column(String(20), index=True)
    repo_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    stars: Mapped[str] = mapped_column(String(40), default="")
    language: Mapped[str] = mapped_column(String(40), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(80), default="")
    category: Mapped[str] = mapped_column(String(40), default="news")
    summary: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title_en: Mapped[str] = mapped_column(String(160))
    title_zh: Mapped[str] = mapped_column(String(160))
    body_en: Mapped[str] = mapped_column(Text, default="")
    body_zh: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    popup: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    list_url: Mapped[str] = mapped_column(String(500), default="")
    keyword: Mapped[str] = mapped_column(String(120), default="")
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    interval_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="idle")
    message: Mapped[str] = mapped_column(String(500), default="")
    found_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, index=True)
    message: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CrawlItem(Base):
    __tablename__ = "crawl_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_jobs.id"), nullable=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    title: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    logo_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MailSetting(Base):
    __tablename__ = "mail_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gmail_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    netease_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sendgrid_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mailgun_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ses_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_default: Mapped[bool] = mapped_column(Boolean, default=False)
    money_dm: Mapped[bool] = mapped_column(Boolean, default=False)
    gmail_host: Mapped[str] = mapped_column(String(120), default="")
    gmail_port: Mapped[int] = mapped_column(Integer, default=0)
    gmail_user: Mapped[str] = mapped_column(String(200), default="")
    gmail_pass: Mapped[str] = mapped_column(String(200), default="")
    gmail_from: Mapped[str] = mapped_column(String(200), default="")
    gmail_from_name: Mapped[str] = mapped_column(String(80), default="")
    netease_host: Mapped[str] = mapped_column(String(120), default="")
    netease_port: Mapped[int] = mapped_column(Integer, default=0)
    netease_user: Mapped[str] = mapped_column(String(200), default="")
    netease_pass: Mapped[str] = mapped_column(String(200), default="")
    netease_from: Mapped[str] = mapped_column(String(200), default="")
    netease_from_name: Mapped[str] = mapped_column(String(80), default="")
    sendgrid_key: Mapped[str] = mapped_column(String(300), default="")
    sendgrid_from: Mapped[str] = mapped_column(String(200), default="")
    sendgrid_from_name: Mapped[str] = mapped_column(String(80), default="")
    mailgun_key: Mapped[str] = mapped_column(String(300), default="")
    mailgun_domain: Mapped[str] = mapped_column(String(200), default="")
    mailgun_region: Mapped[str] = mapped_column(String(20), default="")
    mailgun_from: Mapped[str] = mapped_column(String(200), default="")
    mailgun_from_name: Mapped[str] = mapped_column(String(80), default="")


class MailTask(Base):
    __tablename__ = "mail_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(String(20), default="all")
    run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeedbackNote(Base):
    __tablename__ = "feedback_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedbacks.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="user")
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MailLog(Base):
    __tablename__ = "mail_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient: Mapped[str] = mapped_column(String(200), default="")
    subject: Mapped[str] = mapped_column(String(200), default="")
    channel: Mapped[str] = mapped_column(String(20), default="log")
    status: Mapped[str] = mapped_column(String(20), default="logged")
    message: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
