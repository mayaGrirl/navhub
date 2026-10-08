"""Refresh directory links for AI, cross-border, midnight media, and Telegram."""

import threading
import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Category, Link, Tab
from app.urls import norm_url

CATALOG = {
    "ai": {
        "writing": [("https://www.kimi.com", "Kimi"), ("https://yiyan.baidu.com", "文心一言"), ("https://tongyi.aliyun.com", "通义千问"), ("https://chat.qwen.ai", "Qwen"), ("https://www.doubao.com", "豆包")],
        "image": [("https://jimeng.jianying.com", "即梦"), ("https://www.liblib.art", "Liblib"), ("https://klingai.com", "可灵"), ("https://openai.com/dall-e-3", "DALL-E")],
        "video-tools": [("https://klingai.com", "可灵"), ("https://lumalabs.ai", "Luma"), ("https://www.capcut.com", "剪映")],
        "office": [("https://www.wps.cn", "WPS"), ("https://docs.qq.com", "腾讯文档"), ("https://www.microsoft.com/microsoft-365/copilot", "Copilot")],
        "chat": [("https://chat.baidu.com", "百度AI"), ("https://yuanbao.tencent.com", "腾讯元宝"), ("https://gemini.google.com", "Gemini")],
        "agents": [("https://www.coze.com", "Coze"), ("https://github.com/Significant-Gravitas/AutoGPT", "AutoGPT")],
        "coding": [("https://www.trae.ai", "Trae"), ("https://codeium.com", "Windsurf"), ("https://claude.ai/code", "Claude Code")],
        "dev-platform": [("https://platform.openai.com", "OpenAI"), ("https://bigmodel.cn", "智谱"), ("https://cloud.baidu.com", "百度智能云")],
        "design": [("https://www.gaoding.com", "稿定设计"), ("https://www.chuangkit.com", "创客贴")],
        "audio-tools": [("https://www.ttsmaker.com", "TTSMaker"), ("https://fish.audio", "Fish Audio")],
        "search": [("https://www.n.cn", "纳米搜索"), ("https://chat.baidu.com", "百度搜索AI")],
        "learning": [("https://www.bilibili.com", "哔哩哔哩"), ("https://www.icourse163.org", "中国大学MOOC")],
        "training": [("https://www.modelscope.cn", "魔搭"), ("https://www.paddlepaddle.org.cn", "飞桨")],
        "eval": [("https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard", "Arena")],
        "moderation": [("https://platform.openai.com/docs/guides/moderation", "OpenAI Moderation")],
        "prompts": [("https://promptbase.com", "PromptBase")],
        "side-hustle": [("https://www.capcut.com", "CapCut")],
        "cross-border-ai": [("https://www.sellersprite.com", "卖家精灵"), ("https://www.sorftime.com", "Sorftime")],
        "reading": [("https://www.language-reader.com", "Language Reader")],
    },
    "cross-border": {
        "suite": [("https://www.sellersprite.com", "卖家精灵"), ("https://www.sorftime.com", "Sorftime"), ("https://www.maijiaw.com", "卖家网")],
        "erp": [("https://www.mabangerp.com", "马帮"), ("https://www.dianxiaomi.com", "店小秘"), ("https://www.tongtool.com", "通途")],
        "recommend": [("https://www.amz123.com", "AMZ123"), ("https://www.cifnews.com", "雨果跨境")],
        "onboarding": [("https://seller.kuajingmaihuo.com", "跨境卖货"), ("https://sellercentral.amazon.com", "Seller Central")],
        "logistics": [("https://www.4px.com", "递四方"), ("https://www.yanwenexpress.com", "燕文"), ("https://www.sf-international.com", "顺丰国际")],
        "payments": [("https://www.airwallex.com", "Airwallex"), ("https://www.lianlianpay.com", "连连"), ("https://www.sunrate.com", "寻汇")],
        "sourcing": [("https://www.1688.com", "1688"), ("https://sale.alibaba.com", "Alibaba")],
        "sea": [("https://seller.shopee.cn", "Shopee"), ("https://sellercenter.lazada.com", "Lazada")],
        "social": [("https://www.facebook.com/business", "Meta商务"), ("https://ads.tiktok.com", "TikTok Ads")],
        "proxy-ip": [("https://www.ipidea.net", "IPIDEA"), ("https://www.kookeey.com", "Kookeey")],
        "video-edit": [("https://www.capcut.com", "CapCut"), ("https://www.meitu.com", "美图")],
        "fingerprint": [("https://www.hubstudio.cn", "Hubstudio"), ("https://www.adspower.net", "AdsPower")],
        "sms": [("https://www.twilio.com", "Twilio")],
        "supply": [("https://www.1688.com", "1688"), ("https://cjdropshipping.com", "CJ")],
        "ip-tax": [("https://www.wipo.int", "WIPO"), ("https://sbj.cnipa.gov.cn", "商标局")],
        "training-svc": [("https://www.cifnews.com", "雨果跨境")],
        "platforms": [("https://www.aliexpress.com", "AliExpress"), ("https://www.wish.com", "Wish"), ("https://www.temu.com", "Temu")],
        "other": [("https://www.17track.net", "17TRACK")],
    },
    "media": {
        "video": [("https://www.youtube.com", "YouTube"), ("https://www.bilibili.com", "哔哩哔哩"), ("https://www.youku.com", "优酷"), ("https://v.qq.com", "腾讯视频")],
        "shorts": [("https://www.tiktok.com", "TikTok"), ("https://www.douyin.com", "抖音"), ("https://www.kuaishou.com", "快手")],
        "live": [("https://www.twitch.tv", "Twitch"), ("https://www.huya.com", "虎牙"), ("https://live.bilibili.com", "哔哩直播")],
        "shows": [("https://www.netflix.com", "Netflix"), ("https://www.iqiyi.com", "爱奇艺"), ("https://www.disneyplus.com", "Disney+")],
        "music": [("https://music.163.com", "网易云音乐"), ("https://y.qq.com", "QQ音乐"), ("https://open.spotify.com", "Spotify")],
        "news-media": [("https://www.bbc.com", "BBC"), ("https://www.reuters.com", "路透"), ("https://www.thepaper.cn", "澎湃"), ("https://news.qq.com", "腾讯新闻")],
        "adult-video": [("https://www.pornhub.com", "Pornhub"), ("https://www.xvideos.com", "XVideos"), ("https://www.xhamster.com", "xHamster")],
        "adult-live": [("https://www.chaturbate.com", "Chaturbate"), ("https://www.stripchat.com", "Stripchat"), ("https://www.bongacams.com", "BongaCams")],
        "adult-pics": [("https://www.imagefap.com", "ImageFap"), ("https://www.reddit.com/r/nsfw", "Reddit NSFW")],
        "adult-forum": [("https://www.reddit.com/r/porn", "Reddit")],
        "adult-read": [("https://www.literotica.com", "Literotica")],
        "adult-anime": [("https://www.fakku.net", "FAKKU")],
    },
    "telegram": {
        "news": [("https://t.me/bbcchinese", "BBC中文"), ("https://t.me/reuters", "Reuters"), ("https://t.me/zaobaosg", "早报"), ("https://t.me/durov", "Durov")],
        "tech": [("https://t.me/githubstatus", "GitHub"), ("https://t.me/openai", "OpenAI"), ("https://t.me/deeplearningai", "DeepLearning")],
        "finance": [("https://t.me/financialtimes", "FT"), ("https://t.me/bloomberg", "Bloomberg")],
        "learn": [("https://t.me/pythontelegrambotgroup", "Python Bot"), ("https://t.me/rustlang_ru", "Rust")],
        "fun": [("https://t.me/youtube", "YouTube"), ("https://t.me/netflix", "Netflix")],
        "tools": [("https://t.me/tgandroid", "Telegram Android"), ("https://t.me/telegram", "Telegram")],
        "cross": [("https://t.me/amazonnews", "Amazon"), ("https://t.me/shopify", "Shopify")],
        "groups": [("https://t.me/telegram", "Telegram"), ("https://t.me/tginfo", "TG Info")],
    },
}

TITLES = {
    "media": {
        "adult-video": ("Adult video", "成人视频"),
        "adult-live": ("Adult live", "成人直播"),
        "adult-pics": ("Adult pics", "成人图库"),
        "adult-forum": ("Adult forum", "成人论坛"),
        "adult-read": ("Adult fiction", "成人小说"),
        "adult-anime": ("Adult anime", "成人动漫"),
    },
    "telegram": {
        "news": ("News", "新闻频道"),
        "tech": ("Tech", "科技频道"),
        "finance": ("Finance", "财经频道"),
        "learn": ("Learning", "学习频道"),
        "fun": ("Entertainment", "娱乐频道"),
        "tools": ("Tools", "工具频道"),
        "cross": ("Commerce", "跨境频道"),
        "groups": ("Groups", "群组目录"),
    },
}


def favicon(url: str) -> str:
    host = url.split("/")[2]
    return f"https://www.google.com/s2/favicons?domain={host}&sz=64"


def ensure_tabs(db) -> None:
    media = db.scalar(select(Tab).where(Tab.slug == "media"))
    if media:
        media.title_zh = "午夜媒体"
        media.title_en = "Night Media"
        media.adult = True
        media.visible = True
    adult = db.scalar(select(Tab).where(Tab.slug == "adult"))
    if adult:
        adult.visible = False
    if not db.scalar(select(Tab).where(Tab.slug == "telegram")):
        db.add(Tab(slug="telegram", title_en="Telegram", title_zh="TG群", kind="links", sort=7, visible=True, adult=False))
    db.flush()


def refresh() -> int:
    db = SessionLocal()
    added = 0
    try:
        ensure_tabs(db)
        for tab_slug, categories in {**{k: {} for k in CATALOG}, **TITLES}.items():
            pass
        for tab_slug, categories in TITLES.items():
            tab = db.scalar(select(Tab).where(Tab.slug == tab_slug))
            if not tab:
                continue
            for index, (slug, (en, zh)) in enumerate(categories.items()):
                row = db.scalar(select(Category).where(Category.tab_id == tab.id, Category.slug == slug))
                if not row:
                    db.add(Category(tab_id=tab.id, slug=slug, title_en=en, title_zh=zh, sort=40 + index, visible=True))
        db.flush()
        for tab_slug, categories in CATALOG.items():
            tab = db.scalar(select(Tab).where(Tab.slug == tab_slug))
            if not tab or not tab.auto_crawl:
                continue
            for slug, sites in categories.items():
                category = db.scalar(select(Category).where(Category.tab_id == tab.id, Category.slug == slug))
                if not category:
                    continue
                for url, name in sites:
                    key = norm_url(url)
                    if db.scalar(select(Link.id).where(Link.norm_url == key)):
                        continue
                    db.add(
                        Link(
                            category_id=category.id,
                            title_en=name,
                            title_zh=name,
                            description_en="Official or public page.",
                            description_zh="公开站点。",
                            url=url,
                            norm_url=key,
                            logo_url=favicon(url),
                            status="published",
                            source="crawl",
                            is_hot=True,
                            counts_ready=True,
                            clicks_ready=True,
                        )
                    )
                    added += 1
        db.commit()
        print("directory", added)
        return added
    finally:
        db.close()


def schedule_directory() -> None:
    def loop():
        time.sleep(45 * 60)
        while True:
            try:
                from crawl_boards import sync
                from app.seed import ensure_misc, ensure_world

                db = SessionLocal()
                try:
                    ensure_misc(db)
                    ensure_world(db)
                    db.commit()
                finally:
                    db.close()
                refresh()
                sync()
            except Exception as exc:
                print("directory sync failed", exc.__class__.__name__)
            time.sleep(60 * 60 * 24 * 2)

    threading.Thread(target=loop, daemon=True).start()


if __name__ == "__main__":
    refresh()
