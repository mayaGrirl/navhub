from sqlalchemy import select

from app.crawl import fetch_meta
from app.db import SessionLocal
from app.models import Category, Link, Tab

TITLES = {
    "ai": {
        "writing": ("Writing", "写作助手"),
        "image": ("Images", "图像生成"),
        "video-tools": ("Video", "视频生成"),
        "office": ("Office", "办公助手"),
        "chat": ("Chat", "聊天助手"),
        "agents": ("Agents", "智能代理"),
        "coding": ("Coding", "编程助手"),
        "dev-platform": ("Platforms", "开发平台"),
        "design": ("Design", "设计助手"),
        "audio-tools": ("Audio", "音频生成"),
        "search": ("Search", "搜索引擎"),
        "learning": ("Learning", "学习网站"),
        "training": ("Training", "模型训练"),
        "eval": ("Evaluation", "模型评测"),
        "moderation": ("Moderation", "内容检测"),
        "prompts": ("Prompts", "提示指令"),
        "side-hustle": ("Side work", "副业工具"),
        "cross-border-ai": ("Cross-border", "跨境助手"),
        "reading": ("Reading", "阅读助手"),
    },
    "cross-border": {
        "suite": ("Suites", "综合软件"),
        "erp": ("ERP", "企业系统"),
        "recommend": ("Research", "推荐服务"),
        "onboarding": ("Onboarding", "入驻通道"),
        "logistics": ("Logistics", "物流仓储"),
        "payments": ("Payments", "收款支付"),
        "sourcing": ("Sourcing", "选品参考"),
        "sea": ("SE Asia", "东南亚站"),
        "social": ("Social", "社交媒体"),
        "proxy-ip": ("Proxies", "代理服务"),
        "video-edit": ("Editing", "视频剪辑"),
        "fingerprint": ("Browsers", "指纹环境"),
        "sms": ("SMS", "短信服务"),
        "supply": ("Suppliers", "货源网站"),
        "ip-tax": ("IP and tax", "知产财税"),
        "training-svc": ("Training", "培训服务"),
        "platforms": ("Marketplaces", "跨境平台"),
        "other": ("Other", "其他工具"),
    },
}

SITES = {
    ("ai", "video-tools"): [("https://runwayml.com", "Runway", False, True), ("https://pika.art", "Pika", True, False), ("https://www.heygen.com", "HeyGen", False, True)],
    ("ai", "office"): [("https://gamma.app", "Gamma", True, True), ("https://www.beautiful.ai", "Beautiful.ai", False, False), ("https://tome.app", "Tome", True, False)],
    ("ai", "agents"): [("https://www.coze.cn", "Coze", True, True), ("https://dify.ai", "Dify", True, True), ("https://relevanceai.com", "Relevance AI", False, False)],
    ("ai", "dev-platform"): [("https://huggingface.co", "Hugging Face", True, True), ("https://replicate.com", "Replicate", True, False), ("https://www.together.ai", "Together", False, False)],
    ("ai", "design"): [("https://www.canva.com", "Canva", True, True), ("https://www.figma.com", "Figma", True, True), ("https://looka.com", "Looka", False, False)],
    ("ai", "audio-tools"): [("https://suno.com", "Suno", True, True), ("https://elevenlabs.io", "ElevenLabs", True, True), ("https://www.udio.com", "Udio", True, False)],
    ("ai", "search"): [("https://www.perplexity.ai", "Perplexity", True, True), ("https://metaso.cn", "秘塔搜索", True, True), ("https://you.com", "You.com", True, False)],
    ("ai", "learning"): [("https://www.deeplearning.ai", "DeepLearning.AI", True, True), ("https://www.fast.ai", "fast.ai", True, False), ("https://www.coursera.org", "Coursera", True, False)],
    ("ai", "training"): [("https://wandb.ai", "Weights & Biases", True, False), ("https://lightning.ai", "Lightning", True, False), ("https://modal.com", "Modal", False, False)],
    ("ai", "eval"): [("https://chat.lmsys.org", "LMSYS", True, True), ("https://artificialanalysis.ai", "Artificial Analysis", True, False), ("https://scale.com", "Scale", False, False)],
    ("ai", "moderation"): [("https://sightengine.com", "Sightengine", False, False), ("https://copyleaks.com", "Copyleaks", True, False), ("https://www.originality.ai", "Originality", False, False)],
    ("ai", "prompts"): [("https://promptbase.com", "PromptBase", False, False), ("https://flowgpt.com", "FlowGPT", True, True), ("https://promptperfect.jina.ai", "PromptPerfect", True, False)],
    ("ai", "side-hustle"): [("https://writesonic.com", "Writesonic", True, False), ("https://www.copy.ai", "Copy.ai", True, False), ("https://poe.com", "Poe", True, True)],
    ("ai", "cross-border-ai"): [("https://www.helium10.com", "Helium 10", False, True), ("https://www.junglescout.com", "Jungle Scout", False, True), ("https://www.sellerapp.com", "SellerApp", False, False)],
    ("ai", "reading"): [("https://speechify.com", "Speechify", True, True), ("https://www.naturalreaders.com", "NaturalReader", True, False), ("https://readwise.io", "Readwise", False, False)],
    ("cross-border", "suite"): [("https://www.helium10.com", "Helium 10", False, True), ("https://www.junglescout.com", "Jungle Scout", False, False)],
    ("cross-border", "erp"): [("https://www.odoo.com", "Odoo", True, True), ("https://www.kingdee.com", "金蝶", False, True), ("https://www.yonyou.com", "用友", False, False)],
    ("cross-border", "recommend"): [("https://www.similarweb.com", "Similarweb", True, True), ("https://trends.google.com", "Google Trends", True, True)],
    ("cross-border", "onboarding"): [("https://sell.amazon.com", "Amazon Sell", False, True), ("https://merchant.walmart.com", "Walmart", False, False)],
    ("cross-border", "payments"): [("https://www.payoneer.com", "Payoneer", False, True), ("https://www.pingpongx.com", "PingPong", False, True), ("https://www.worldfirst.com", "WorldFirst", False, False)],
    ("cross-border", "sea"): [("https://shopee.com", "Shopee", False, True), ("https://www.lazada.com", "Lazada", False, True), ("https://seller.tiktok.com", "TikTok Shop", False, True)],
    ("cross-border", "social"): [("https://www.facebook.com", "Facebook", True, True), ("https://www.instagram.com", "Instagram", True, True), ("https://www.tiktok.com", "TikTok", True, True)],
    ("cross-border", "proxy-ip"): [("https://brightdata.com", "Bright Data", False, False), ("https://oxylabs.io", "Oxylabs", False, False)],
    ("cross-border", "video-edit"): [("https://www.capcut.com", "CapCut", True, True), ("https://www.veed.io", "VEED", True, False)],
    ("cross-border", "fingerprint"): [("https://www.adspower.com", "AdsPower", False, True), ("https://multilogin.com", "Multilogin", False, False), ("https://gologin.com", "GoLogin", False, False)],
    ("cross-border", "sms"): [("https://www.twilio.com", "Twilio", True, True), ("https://www.messagebird.com", "Bird", False, False)],
    ("cross-border", "supply"): [("https://www.1688.com", "1688", False, True), ("https://www.alibaba.com", "Alibaba", False, True)],
    ("cross-border", "ip-tax"): [("https://www.wipo.int", "WIPO", True, False), ("https://www.uspto.gov", "USPTO", True, False)],
    ("cross-border", "training-svc"): [("https://sell.amazon.com/learn", "Amazon Learn", True, False), ("https://www.shopify.com/blog", "Shopify Blog", True, False)],
    ("cross-border", "platforms"): [("https://www.ebay.com", "eBay", False, True), ("https://www.shopify.com", "Shopify", True, True), ("https://www.etsy.com", "Etsy", False, False)],
    ("cross-border", "other"): [("https://www.17track.net", "17TRACK", True, True), ("https://www.aftership.com", "AfterShip", True, False)],
}


def favicon(url: str) -> str:
    host = url.split("/")[2]
    return f"https://www.google.com/s2/favicons?domain={host}&sz=64"


def main() -> None:
    db = SessionLocal()
    added = 0
    try:
        for tab_slug, names in TITLES.items():
            tab = db.scalar(select(Tab).where(Tab.slug == tab_slug))
            for slug, (en, zh) in names.items():
                row = db.scalar(select(Category).where(Category.tab_id == tab.id, Category.slug == slug))
                if row:
                    row.title_en, row.title_zh = en, zh
        for (tab_slug, cat_slug), items in SITES.items():
            tab = db.scalar(select(Tab).where(Tab.slug == tab_slug))
            category = db.scalar(select(Category).where(Category.tab_id == tab.id, Category.slug == cat_slug))
            for url, name, is_free, is_hot in items:
                if db.scalar(select(Link).where(Link.url == url)):
                    continue
                description = "Official site."
                logo = favicon(url)
                try:
                    meta = fetch_meta(url)
                    description = (meta["description"] or meta["title"] or description)[:500]
                    logo = (meta["logo_url"] or logo)[:500]
                except Exception:
                    pass
                db.add(
                    Link(
                        category_id=category.id,
                        title_en=name,
                        title_zh=name,
                        description_en=description,
                        description_zh=description,
                        url=url,
                        logo_url=logo,
                        is_free=is_free,
                        is_hot=is_hot,
                        status="published",
                        source="crawl",
                    )
                )
                added += 1
                print("added", cat_slug, name)
        db.commit()
        print("total", added)
    finally:
        db.close()


if __name__ == "__main__":
    main()
