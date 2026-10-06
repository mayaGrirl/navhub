import secrets
import string
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Category, Level, Link, Page, PointRule, Tab, User
from app.urls import norm_url
from app.security import hash_password

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def ensure_gate() -> str:
    gate = (settings.admin_gate or "").strip()
    if gate:
        return gate
    alphabet = string.ascii_letters + string.digits
    gate = "".join(secrets.choice(alphabet) for _ in range(32))
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = [line for line in text.splitlines() if not line.startswith("ADMIN_GATE=")]
    lines.append(f"ADMIN_GATE={gate}")
    ENV_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    settings.admin_gate = gate
    return gate


LEVELS = [
    (0, 0, 5),
    (1, 10, 10),
    (2, 30, 20),
    (3, 60, 30),
    (4, 100, 40),
    (5, 160, 50),
    (6, 240, 60),
    (7, 360, 80),
    (8, 500, 100),
    (9, 700, 120),
    (10, 1000, 150),
]


def ensure_levels(db: Session) -> None:
    db.query(Level).filter(Level.level > 10).delete()
    have = set(db.scalars(select(Level.level)).all())
    for level, points, limit in LEVELS:
        if level not in have:
            db.add(Level(level=level, min_points=points, proxy_per_minute=limit))
    if not db.get(PointRule, 1):
        db.add(PointRule(id=1, points_per_link=1))


def seed_mark_counts(db: Session) -> None:
    import random

    rows = db.scalars(select(Link).where(Link.counts_ready.is_(False))).all()
    for row in rows:
        row.favorite_count = random.randint(6, 96)
        row.recommend_count = random.randint(2, 48)
        row.counts_ready = True
    pending = db.scalars(select(Link).where(Link.clicks_ready.is_(False))).all()
    for row in pending:
        row.click_count = random.randint(12, 240)
        row.clicks_ready = True


MISC = [
    ("friends", "Friends", "友情链接", [
        ("少数派", "SSPAI", "https://sspai.com/", "效率与数字生活"),
        ("小众软件", "Appinn", "https://www.appinn.com/", "新鲜实用的软件"),
        ("设计达人导航", "Shejidaren", "https://hao.shejidaren.com/", "设计师常用网址"),
        ("Product Hunt", "Product Hunt", "https://www.producthunt.com/", "新产品发布"),
        ("AlternativeTo", "AlternativeTo", "https://alternativeto.net/", "软件替代品"),
    ]),
    ("tools", "Online tools", "在线工具", [
        ("TinyPNG", "TinyPNG", "https://tinypng.com/", "压缩图片"),
        ("Squoosh", "Squoosh", "https://squoosh.app/", "浏览器里压缩图片"),
        ("Regex101", "Regex101", "https://regex101.com/", "调试正则"),
        ("Excalidraw", "Excalidraw", "https://excalidraw.com/", "手绘白板"),
        ("Carbon", "Carbon", "https://carbon.now.sh/", "代码截图"),
    ]),
    ("cloud", "Cloud and mail", "云盘邮箱", [
        ("Google 云端硬盘", "Google Drive", "https://drive.google.com/", "文件存储"),
        ("Dropbox", "Dropbox", "https://www.dropbox.com/", "文件同步"),
        ("阿里云盘", "Aliyun Drive", "https://www.alipan.com/", "国内网盘"),
        ("Gmail", "Gmail", "https://mail.google.com/", "邮箱"),
        ("Outlook", "Outlook", "https://outlook.live.com/", "邮箱"),
        ("Proton Mail", "Proton Mail", "https://proton.me/mail", "加密邮箱"),
    ]),
    ("design", "Design assets", "设计素材", [
        ("Unsplash", "Unsplash", "https://unsplash.com/", "免费照片"),
        ("Pexels", "Pexels", "https://www.pexels.com/", "免费图片和视频"),
        ("Google Fonts", "Google Fonts", "https://fonts.google.com/", "字体"),
        ("Iconify", "Iconify", "https://iconify.design/", "图标"),
        ("Coolors", "Coolors", "https://coolors.co/", "配色"),
    ]),
    ("learn", "Learning", "学习文档", [
        ("MDN", "MDN", "https://developer.mozilla.org/", "Web 文档"),
        ("Python 文档", "Python docs", "https://docs.python.org/zh-cn/3/", "Python"),
        ("Vue", "Vue", "https://cn.vuejs.org/", "前端框架"),
        ("可汗学院", "Khan Academy", "https://www.khanacademy.org/", "公开课程"),
        ("维基百科", "Wikipedia", "https://www.wikipedia.org/", "百科"),
    ]),
    ("life", "Daily lookup", "生活查询", [
        ("中国天气", "Weather", "https://www.weather.com.cn/", "天气预报"),
        ("OpenStreetMap", "OpenStreetMap", "https://www.openstreetmap.org/", "地图"),
        ("快递100", "Kuaidi100", "https://www.kuaidi100.com/", "快递查询"),
        ("铁路12306", "12306", "https://www.12306.cn/", "火车票"),
        ("XE", "XE", "https://www.xe.com/", "汇率"),
    ]),
]


def ensure_misc(db: Session) -> None:
    import random

    tab = db.scalar(select(Tab).where(Tab.slug == "misc"))
    if not tab:
        return
    for index, (slug, en, zh, items) in enumerate(MISC):
        category = db.scalar(select(Category).where(Category.tab_id == tab.id, Category.slug == slug))
        if not category:
            category = Category(tab_id=tab.id, slug=slug, title_en=en, title_zh=zh, sort=index, visible=True)
            db.add(category)
            db.flush()
        for title_zh, title_en, url, desc in items:
            key = norm_url(url)
            if db.scalar(select(Link.id).where(Link.norm_url == key)):
                continue
            db.add(
                Link(
                    category_id=category.id,
                    title_en=title_en,
                    title_zh=title_zh,
                    description_en=desc,
                    description_zh=desc,
                    url=url,
                    norm_url=key,
                    status="published",
                    source="admin",
                    favorite_count=random.randint(6, 96),
                    recommend_count=random.randint(2, 48),
                    click_count=random.randint(12, 240),
                    counts_ready=True,
                    clicks_ready=True,
                )
            )


def seed(db: Session) -> str:
    gate = ensure_gate()
    ensure_levels(db)
    seed_mark_counts(db)
    for row in db.scalars(select(Link).where(Link.norm_url == "")).all():
        row.norm_url = norm_url(row.url)
    if not db.scalar(select(User).where(User.email == settings.admin_email)):
        db.add(
            User(
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                role="admin",
            )
        )
    home = db.scalar(select(Tab).where(Tab.slug == "github"))
    if home:
        home.slug = "general"
        home.kind = "home"
    wanted = [
        ("general", "Daily", "每日资讯", "home", 0, True, False),
        ("ai", "AI Tools", "AI工具", "links", 1, True, False),
        ("cross-border", "Cross-border", "跨境电商", "links", 2, True, False),
        ("media", "Night Media", "午夜媒体", "links", 3, True, True),
        ("telegram", "Telegram", "TG群", "links", 4, True, False),
        ("misc", "More", "其他分类", "links", 5, True, False),
        ("resources", "Resources", "资料", "links", 6, False, False),
        ("adult", "Adult", "成人", "links", 7, False, True),
    ]
    for slug, en, zh, kind, sort, visible, adult in wanted:
        row = db.scalar(select(Tab).where(Tab.slug == slug))
        if not row:
            if not db.scalar(select(Tab.id)):
                continue
            row = Tab(slug=slug, title_en=en, title_zh=zh, kind=kind, sort=sort, visible=visible, adult=adult)
            db.add(row)
            continue
        row.title_en = en
        row.title_zh = zh
        row.kind = kind
        row.sort = sort
        row.visible = visible
        row.adult = adult
    if db.scalar(select(Tab.id)):
        ensure_misc(db)
        db.commit()
        return gate

    samples = [
        ("ai", "AI", "AI", "links", False, [("writing", "AI Writing", "AI写作")]),
        ("cross-border", "Cross-border", "跨境电商", "links", False, [("sourcing", "Sourcing", "选品")]),
        ("resources", "Resources", "资料", "links", False, [("reports", "Reports", "报告")]),
        ("media", "Media", "媒体", "links", False, [("video", "Video", "视频")]),
        ("general", "Daily", "每日资讯", "home", False, []),
        ("adult", "Adult", "成人", "links", True, [("sites", "Sites", "站点")]),
    ]
    for index, (slug, en, zh, kind, adult, cats) in enumerate(samples):
        tab = Tab(slug=slug, title_en=en, title_zh=zh, kind=kind, sort=index, adult=adult)
        db.add(tab)
        db.flush()
        for c_index, (c_slug, c_en, c_zh) in enumerate(cats):
            category = Category(tab_id=tab.id, slug=c_slug, title_en=c_en, title_zh=c_zh, sort=c_index)
            db.add(category)
            db.flush()
            if slug == "ai" and c_slug == "writing":
                db.add(
                    Link(
                        category_id=category.id,
                        title_en="Example writer",
                        title_zh="示例写作",
                        description_en="Sample card. Replace it from the admin console.",
                        description_zh="示例卡片，可在后台替换。",
                        url="https://example.com",
                        is_free=True,
                        status="published",
                        source="admin",
                    )
                )

    db.add(
        Page(
            key="about",
            title_en="About",
            title_zh="关于我们",
            body_en="A directory of links. Edit this page in the admin console.",
            body_zh="这是一个链接导航站。请在管理后台编辑本页。",
        )
    )
    db.add(
        Page(
            key="contact",
            title_en="Contact",
            title_zh="联系方式",
            body_en="Site and advertising inquiries both use the contacts below.",
            body_zh="站点事务和广告合作都用下面的联系方式。",
            email="editor@example.com",
        )
    )
    db.add(
        Page(
            key="advertise",
            title_en="Advertise",
            title_zh="广告合作",
            body_en="Advertising slots are managed in the admin console.",
            body_zh="广告位在管理后台配置。",
        )
    )
    db.commit()
    return gate
