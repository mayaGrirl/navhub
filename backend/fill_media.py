"""Fill midnight media: adult directory from ThePornDude, plus public legal media sites."""
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Category, Link, Tab

MINOR = ("teen", "jailbait", "lolita", "underage", "child", "幼女", "未成年", "萝莉")

DUDE = {
    "Free Porn Tube Sites": ("adult-video", "成人视频"),
    "Free OnlyFans Accounts": ("onlyfans-free", "免费订阅"),
    "TikTok Porn Sites": ("adult-shorts", "短视频站"),
    "AI Porn Sites": ("adult-ai", "AI成站"),
    "Sex Chat Sites": ("adult-chat", "色情聊天"),
    "Free OnlyFans Porn Sites": ("onlyfans", "订阅视频"),
    "Live Sex Cam Sites": ("adult-live", "成人直播"),
    "AI Porn Generator Sites": ("adult-gen", "AI生成"),
    "VR Porn Sites": ("adult-vr", "虚拟现实"),
    "Top Premium Porn Sites": ("adult-paid", "付费站点"),
    "Hookup Sites": ("adult-dating", "成人交友"),
    "Premium Amateur Porn Sites": ("adult-amateur", "素人付费"),
}

GENERAL = {
    "video": ("视频平台", [
        ("https://www.youtube.com", "YouTube"), ("https://www.bilibili.com", "哔哩哔哩"),
        ("https://v.qq.com", "腾讯视频"), ("https://www.iqiyi.com", "爱奇艺"),
        ("https://www.youku.com", "优酷"), ("https://www.mgtv.com", "芒果TV"),
        ("https://www.ixigua.com", "西瓜视频"), ("https://tv.sohu.com", "搜狐视频"),
        ("https://www.le.com", "乐视视频"), ("https://www.pptv.com", "PPTV"),
        ("https://www.netflix.com", "Netflix"), ("https://www.primevideo.com", "Prime Video"),
        ("https://www.disneyplus.com", "Disney+"), ("https://www.max.com", "Max"),
        ("https://www.hulu.com", "Hulu"), ("https://www.crunchyroll.com", "Crunchyroll"),
        ("https://www.viki.com", "Viki"), ("https://www.dailymotion.com", "Dailymotion"),
        ("https://vimeo.com", "Vimeo"), ("https://www.twitch.tv", "Twitch"),
    ]),
    "shorts": ("短视频", [
        ("https://www.douyin.com", "抖音"), ("https://www.kuaishou.com", "快手"),
        ("https://www.tiktok.com", "TikTok"), ("https://www.youtube.com/shorts", "YouTube Shorts"),
        ("https://www.xiaohongshu.com", "小红书"), ("https://www.instagram.com/reels", "Instagram Reels"),
        ("https://www.bilibili.com", "哔哩哔哩"), ("https://www.weibo.com", "微博视频"),
    ]),
    "live": ("直播平台", [
        ("https://live.bilibili.com", "哔哩直播"), ("https://www.huya.com", "虎牙"),
        ("https://www.douyu.com", "斗鱼"), ("https://www.douyin.com", "抖音直播"),
        ("https://live.kuaishou.com", "快手直播"), ("https://www.twitch.tv", "Twitch"),
        ("https://www.youtube.com/live", "YouTube Live"), ("https://www.kick.com", "Kick"),
        ("https://cc.163.com", "网易CC"), ("https://www.yy.com", "YY"),
    ]),
    "shows": ("影视剧集", [
        ("https://www.netflix.com", "Netflix"), ("https://www.iqiyi.com", "爱奇艺"),
        ("https://v.qq.com", "腾讯视频"), ("https://www.youku.com", "优酷"),
        ("https://www.mgtv.com", "芒果TV"), ("https://www.disneyplus.com", "Disney+"),
        ("https://www.max.com", "Max"), ("https://www.hulu.com", "Hulu"),
        ("https://www.primevideo.com", "Prime Video"), ("https://tv.apple.com", "Apple TV"),
        ("https://www.paramountplus.com", "Paramount+"), ("https://www.peacocktv.com", "Peacock"),
    ]),
    "anime": ("动漫二次", [
        ("https://www.bilibili.com", "哔哩哔哩"), ("https://www.crunchyroll.com", "Crunchyroll"),
        ("https://www.iq.com", "爱奇艺国际"), ("https://www.netflix.com", "Netflix"),
        ("https://www.youtube.com", "YouTube"), ("https://www.hidive.com", "HIDIVE"),
        ("https://www.funimation.com", "Funimation"), ("https://anime.dmkt-sp.jp", "d动画"),
    ]),
    "music": ("音乐平台", [
        ("https://music.163.com", "网易云音乐"), ("https://y.qq.com", "QQ音乐"),
        ("https://music.apple.com", "Apple Music"), ("https://open.spotify.com", "Spotify"),
        ("https://music.youtube.com", "YouTube Music"), ("https://www.kugou.com", "酷狗"),
        ("https://www.kuwo.cn", "酷我"), ("https://music.migu.cn", "咪咕音乐"),
        ("https://www.xiami.com", "虾米"), ("https://tidal.com", "TIDAL"),
        ("https://soundcloud.com", "SoundCloud"), ("https://bandcamp.com", "Bandcamp"),
    ]),
    "audiobooks": ("有声读物", [
        ("https://www.ximalaya.com", "喜马拉雅"), ("https://www.lrts.me", "懒人听书"),
        ("https://www.qingting.fm", "蜻蜓FM"), ("https://www.audible.com", "Audible"),
        ("https://music.163.com", "网易云阅读"), ("https://yuedu.163.com", "网易云阅读"),
        ("https://www.lizhi.fm", "荔枝"), ("https://storytel.com", "Storytel"),
    ]),
    "radio": ("电台广播", [
        ("https://www.qingting.fm", "蜻蜓FM"), ("https://www.ximalaya.com", "喜马拉雅"),
        ("https://www.radio.cn", "云听"), ("https://www.bbc.co.uk/sounds", "BBC Sounds"),
        ("https://www.npr.org", "NPR"), ("https://tunein.com", "TuneIn"),
        ("https://www.iheart.com", "iHeartRadio"),
    ]),
    "news-media": ("新闻媒体", [
        ("https://www.bbc.com", "BBC"), ("https://www.reuters.com", "路透"),
        ("https://www.thepaper.cn", "澎湃"), ("https://news.qq.com", "腾讯新闻"),
        ("https://www.theguardian.com", "卫报"), ("https://apnews.com", "美联社"),
        ("https://www.nytimes.com", "纽约时报"), ("https://www.ft.com", "金融时报"),
        ("https://www.chinanews.com.cn", "中国新闻网"), ("https://www.people.com.cn", "人民网"),
        ("https://www.xinhuanet.com", "新华网"), ("https://www.caixin.com", "财新"),
    ]),
    "docs": ("纪录影片", [
        ("https://www.netflix.com", "Netflix"), ("https://www.bilibili.com", "哔哩哔哩"),
        ("https://www.youtube.com", "YouTube"), ("https://www.nationalgeographic.com", "国家地理"),
        ("https://www.discovery.com", "Discovery"), ("https://www.curiositystream.com", "Curiosity Stream"),
        ("https://www.pbs.org", "PBS"),
    ]),
    "photos": ("图片社区", [
        ("https://www.xiaohongshu.com", "小红书"), ("https://www.instagram.com", "Instagram"),
        ("https://www.pinterest.com", "Pinterest"), ("https://500px.com", "500px"),
        ("https://www.flickr.com", "Flickr"), ("https://unsplash.com", "Unsplash"),
        ("https://www.lofter.com", "LOFTER"), ("https://huaban.com", "花瓣"),
    ]),
    "paid": ("知识付费", [
        ("https://www.zhihu.com", "知乎"), ("https://www.dedao.cn", "得到"),
        ("https://www.ximalaya.com", "喜马拉雅"), ("https://www.icourse163.org", "中国大学MOOC"),
        ("https://www.coursera.org", "Coursera"), ("https://www.udemy.com", "Udemy"),
        ("https://www.skillshare.com", "Skillshare"), ("https://www.masterclass.com", "MasterClass"),
    ]),
    "sports-live": ("体育直播", [
        ("https://www.miguvideo.com", "咪咕视频"), ("https://sports.cctv.com", "央视体育"),
        ("https://www.espn.com", "ESPN"), ("https://www.nba.com", "NBA"),
        ("https://www.huya.com", "虎牙"), ("https://www.douyu.com", "斗鱼"),
        ("https://www.dazn.com", "DAZN"), ("https://www.olympics.com", "奥运"),
    ]),
    "game-news": ("游戏资讯", [
        ("https://www.3dmgame.com", "3DM"), ("https://www.gamersky.com", "游民星空"),
        ("https://www.ign.com", "IGN"), ("https://www.polygon.com", "Polygon"),
        ("https://www.gcores.com", "机核"), ("https://store.steampowered.com", "Steam"),
        ("https://www.taptap.cn", "TapTap"), ("https://www.playstation.com", "PlayStation"),
    ]),
    "podcasts": ("播客节目", [
        ("https://www.xiaoyuzhoufm.com", "小宇宙"), ("https://podcasts.apple.com", "Apple 播客"),
        ("https://open.spotify.com", "Spotify"), ("https://www.ximalaya.com", "喜马拉雅"),
        ("https://pocketcasts.com", "Pocket Casts"), ("https://www.youtube.com", "YouTube"),
    ]),
    "audio": ("音频播客", [
        ("https://www.ximalaya.com", "喜马拉雅"), ("https://soundcloud.com", "SoundCloud"),
        ("https://www.qingting.fm", "蜻蜓FM"), ("https://music.163.com", "网易云音乐"),
    ]),
}


def bad(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in MINOR)


def favicon(url: str) -> str:
    host = url.split("/")[2]
    return f"https://www.google.com/s2/favicons?domain={host}&sz=64"


def ensure(db, tab_id, slug, title, sort):
    row = db.scalar(select(Category).where(Category.tab_id == tab_id, Category.slug == slug))
    if not row:
        row = Category(tab_id=tab_id, slug=slug, title_en=title, title_zh=title, sort=sort, visible=True)
        db.add(row)
        db.flush()
    else:
        row.title_zh = title
        row.visible = True
    return row


def add_link(db, category_id, name, url):
    url = url[:500]
    if bad(name) or bad(url):
        return False
    if db.scalar(select(Link).where(Link.category_id == category_id, Link.url == url)):
        return False
    db.add(Link(
        category_id=category_id, title_en=name[:160], title_zh=name[:160],
        url=url, logo_url=favicon(url), status="published", source="crawl",
    ))
    return True


def main():
    db = SessionLocal()
    tab = db.scalar(select(Tab).where(Tab.slug == "media"))
    if not tab or not tab.auto_crawl:
        db.close()
        return 0
    added = 0
    import httpx

    response = httpx.get("https://theporndude.com/zh", timeout=40, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    seen = {}
    for anchor in soup.select("a.link-analytics"):
        cat = anchor.get("data-category") or "Free Porn Tube Sites"
        href = (anchor.get("href") or "").strip()
        if cat not in DUDE or not href.startswith("http"):
            continue
        if "theporndude.com" in href:
            continue
        name = anchor.get_text(strip=True)
        seen.setdefault(cat, []).append((name, href))
    sort = 50
    for cat, items in seen.items():
        slug, title = DUDE[cat]
        row = ensure(db, tab.id, slug, title, sort)
        sort += 1
        for name, href in items:
            if add_link(db, row.id, name, href):
                added += 1
    for slug, (title, items) in GENERAL.items():
        row = ensure(db, tab.id, slug, title, sort)
        sort += 1
        for url, name in items:
            if add_link(db, row.id, name, url):
                added += 1
    db.commit()
    print("added", added, "dude cats", len(seen))


if __name__ == "__main__":
    main()
