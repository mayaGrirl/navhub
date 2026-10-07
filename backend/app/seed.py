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
    ("navs", "Directories", "导航站点", [
        ("hao123", "hao123", "https://www.hao123.com/", "综合网址导航"),
        ("360导航", "360 Navigation", "https://hao.360.com/", "综合网址导航"),
        ("搜狗网址导航", "Sogou Navigation", "https://123.sogou.com/", "综合网址导航"),
        ("未代导航", "WDNav", "https://wdnav.com/", "实用网址导航"),
        ("一点导航", "One Click Nav", "https://oneclicknav.cn/", "资源信息导航"),
        ("终极导航", "ZJNav", "https://www.zjnav.com/", "网址导航大全"),
        ("Curlie", "Curlie", "https://curlie.org/", "全球开放目录"),
        ("Yahoo", "Yahoo", "https://www.yahoo.com/", "综合门户"),
        ("Naver", "Naver", "https://www.naver.com/", "韩国门户"),
        ("Yahoo Japan", "Yahoo Japan", "https://www.yahoo.co.jp/", "日本门户"),
    ]),
    ("search", "Search", "搜索引擎", [
        ("Google", "Google", "https://www.google.com/", "网页搜索"),
        ("Bing", "Bing", "https://www.bing.com/", "网页搜索"),
        ("百度", "Baidu", "https://www.baidu.com/", "中文搜索"),
        ("DuckDuckGo", "DuckDuckGo", "https://duckduckgo.com/", "少追踪的搜索"),
        ("搜狗", "Sogou", "https://www.sogou.com/", "中文搜索"),
        ("Yandex", "Yandex", "https://yandex.com/", "网页搜索"),
        ("Qwant", "Qwant", "https://www.qwant.com/", "法国搜索"),
        ("Ecosia", "Ecosia", "https://www.ecosia.org/", "欧洲搜索"),
        ("Naver", "Naver", "https://search.naver.com/", "韩国搜索"),
        ("Yahoo Japan", "Yahoo Japan", "https://search.yahoo.co.jp/", "日本搜索"),
        ("Startpage", "Startpage", "https://www.startpage.com/", "隐私搜索"),
    ]),
    ("community", "Communities", "社区问答", [
        ("知乎", "Zhihu", "https://www.zhihu.com/", "问答社区"),
        ("V2EX", "V2EX", "https://www.v2ex.com/", "创意工作者社区"),
        ("稀土掘金", "Juejin", "https://juejin.cn/", "技术社区"),
        ("Stack Overflow", "Stack Overflow", "https://stackoverflow.com/", "编程问答"),
        ("Hacker News", "Hacker News", "https://news.ycombinator.com/", "技术讨论"),
        ("Reddit", "Reddit", "https://www.reddit.com/", "兴趣社区"),
    ]),
    ("news", "News", "新闻媒体", [
        ("BBC 中文", "BBC Chinese", "https://www.bbc.com/zhongwen/simp", "国际新闻"),
        ("路透", "Reuters", "https://www.reuters.com/", "国际新闻"),
        ("澎湃新闻", "The Paper", "https://www.thepaper.cn/", "中文新闻"),
        ("联合早报", "Zaobao", "https://www.zaobao.com.sg/", "中文新闻"),
        ("美联社", "AP", "https://apnews.com/", "国际新闻"),
        ("华尔街日报中文", "WSJ Chinese", "https://cn.wsj.com/", "财经新闻"),
        ("The Guardian", "The Guardian", "https://www.theguardian.com/", "英国新闻"),
        ("纽约时报", "New York Times", "https://www.nytimes.com/", "美国新闻"),
        ("NHK", "NHK", "https://www3.nhk.or.jp/news/", "日本新闻"),
        ("德国之声", "DW", "https://www.dw.com/", "德国新闻"),
        ("半岛电视台", "Al Jazeera", "https://www.aljazeera.com/", "国际新闻"),
        ("Le Monde", "Le Monde", "https://www.lemonde.fr/", "法国新闻"),
        ("朝日新闻", "Asahi", "https://www.asahi.com/", "日本新闻"),
    ]),
    ("courses", "Courses", "在线课程", [
        ("中国大学MOOC", "iCourse", "https://www.icourse163.org/", "大学公开课"),
        ("Coursera", "Coursera", "https://www.coursera.org/", "大学课程"),
        ("edX", "edX", "https://www.edx.org/", "大学课程"),
        ("网易公开课", "Open Course", "https://open.163.com/", "公开课"),
        ("学堂在线", "XuetangX", "https://www.xuetangx.com/", "大学课程"),
        ("国家智慧教育", "SmartEdu", "https://www.smartedu.cn/", "教育资源"),
    ]),
    ("translate", "Translate", "翻译词典", [
        ("DeepL", "DeepL", "https://www.deepl.com/translator", "机器翻译"),
        ("Google 翻译", "Google Translate", "https://translate.google.com/", "机器翻译"),
        ("有道词典", "Youdao", "https://www.youdao.com/", "词典"),
        ("剑桥词典", "Cambridge", "https://dictionary.cambridge.org/", "英英词典"),
        ("牛津学习者词典", "Oxford", "https://www.oxfordlearnersdictionaries.com/", "英语词典"),
    ]),
    ("shop", "Shopping", "购物商城", [
        ("淘宝", "Taobao", "https://www.taobao.com/", "综合购物"),
        ("京东", "JD", "https://www.jd.com/", "综合购物"),
        ("拼多多", "Pinduoduo", "https://www.pinduoduo.com/", "综合购物"),
        ("天猫", "Tmall", "https://www.tmall.com/", "品牌购物"),
        ("亚马逊", "Amazon", "https://www.amazon.com/", "海外购物"),
        ("唯品会", "Vipshop", "https://www.vip.com/", "品牌特卖"),
        ("eBay", "eBay", "https://www.ebay.com/", "全球拍卖"),
        ("乐天", "Rakuten", "https://www.rakuten.co.jp/", "日本购物"),
        ("Mercado Libre", "Mercado Libre", "https://www.mercadolibre.com/", "拉美购物"),
        ("Shopee", "Shopee", "https://shopee.sg/", "东南亚购物"),
        ("Coupang", "Coupang", "https://www.coupang.com/", "韩国购物"),
        ("Etsy", "Etsy", "https://www.etsy.com/", "手作市集"),
    ]),
    ("video", "Video", "视频平台", [
        ("哔哩哔哩", "Bilibili", "https://www.bilibili.com/", "视频社区"),
        ("YouTube", "YouTube", "https://www.youtube.com/", "视频"),
        ("优酷", "Youku", "https://www.youku.com/", "长视频"),
        ("腾讯视频", "Tencent Video", "https://v.qq.com/", "长视频"),
        ("爱奇艺", "iQIYI", "https://www.iqiyi.com/", "长视频"),
        ("抖音", "Douyin", "https://www.douyin.com/", "短视频"),
    ]),
    ("music", "Music", "音乐音频", [
        ("网易云音乐", "NetEase Music", "https://music.163.com/", "音乐"),
        ("QQ 音乐", "QQ Music", "https://y.qq.com/", "音乐"),
        ("Spotify", "Spotify", "https://open.spotify.com/", "音乐"),
        ("喜马拉雅", "Ximalaya", "https://www.ximalaya.com/", "有声"),
        ("SoundCloud", "SoundCloud", "https://soundcloud.com/", "音乐"),
    ]),
    ("social", "Social", "社交网络", [
        ("微博", "Weibo", "https://weibo.com/", "社交"),
        ("小红书", "Xiaohongshu", "https://www.xiaohongshu.com/", "生活方式"),
        ("X", "X", "https://x.com/", "社交"),
        ("LinkedIn", "LinkedIn", "https://www.linkedin.com/", "职业社交"),
        ("豆瓣", "Douban", "https://www.douban.com/", "书影音社区"),
        ("即刻", "Jike", "https://web.okjike.com/", "兴趣社区"),
    ]),
    ("jobs", "Jobs", "招聘求职", [
        ("BOSS 直聘", "BOSS Zhipin", "https://www.zhipin.com/", "招聘"),
        ("智联招聘", "Zhaopin", "https://www.zhaopin.com/", "招聘"),
        ("前程无忧", "51job", "https://www.51job.com/", "招聘"),
        ("猎聘", "Liepin", "https://www.liepin.com/", "招聘"),
        ("LinkedIn Jobs", "LinkedIn Jobs", "https://www.linkedin.com/jobs/", "海外职位"),
        ("国家大学生就业", "NCSS", "https://www.ncss.cn/", "高校就业"),
    ]),
    ("travel", "Travel", "出行旅游", [
        ("携程", "Trip.com", "https://www.ctrip.com/", "旅行预订"),
        ("飞猪", "Fliggy", "https://www.fliggy.com/", "旅行预订"),
        ("铁路12306", "12306", "https://www.12306.cn/", "火车票"),
        ("航旅纵横", "Umetrip", "https://www.umetrip.com/", "航班"),
        ("高德地图", "Amap", "https://www.amap.com/", "地图导航"),
        ("Booking", "Booking", "https://www.booking.com/", "酒店"),
    ]),
    ("money", "Finance", "财经银行", [
        ("东方财富", "Eastmoney", "https://www.eastmoney.com/", "财经行情"),
        ("雪球", "Xueqiu", "https://xueqiu.com/", "投资社区"),
        ("英为财情", "Investing", "https://cn.investing.com/", "全球行情"),
        ("中国人民银行", "PBOC", "https://www.pbc.gov.cn/", "央行"),
        ("上交所", "SSE", "https://www.sse.com.cn/", "证券交易所"),
        ("深交所", "SZSE", "https://www.szse.cn/", "证券交易所"),
    ]),
    ("gov", "Public services", "政务服务", [
        ("中国政府网", "gov.cn", "https://www.gov.cn/", "政府门户"),
        ("国家政务服务", "Gov Service", "https://www.gjzwfw.gov.cn/", "政务服务"),
        ("国家企业信用", "GSXT", "https://www.gsxt.gov.cn/", "企业信用"),
        ("中国裁判文书网", "Court Judgments", "https://wenshu.court.gov.cn/", "裁判文书"),
        ("个人所得税", "Personal Tax", "https://etax.chinatax.gov.cn/", "个税"),
        ("国家医保服务", "Medical Insurance", "https://fuwu.nhsa.gov.cn/", "医保"),
        ("USA.gov", "USA.gov", "https://www.usa.gov/", "美国政府"),
        ("GOV.UK", "GOV.UK", "https://www.gov.uk/", "英国政府"),
        ("日本政府", "Japan Gov", "https://www.japan.go.jp/", "日本政府"),
        ("欧盟", "European Union", "https://european-union.europa.eu/", "欧盟"),
        ("加拿大政府", "Canada", "https://www.canada.ca/", "加拿大政府"),
        ("澳大利亚政府", "Australia", "https://www.australia.gov.au/", "澳大利亚政府"),
        ("印度政府", "India", "https://www.india.gov.in/", "印度政府"),
        ("韩国政府", "Korea", "https://www.gov.kr/", "韩国政府"),
        ("新加坡政府", "Singapore", "https://www.gov.sg/", "新加坡政府"),
    ]),
    ("games", "Games", "游戏平台", [
        ("Steam", "Steam", "https://store.steampowered.com/", "游戏商店"),
        ("Epic", "Epic Games", "https://store.epicgames.com/", "游戏商店"),
        ("TapTap", "TapTap", "https://www.taptap.cn/", "游戏社区"),
        ("任天堂", "Nintendo", "https://www.nintendo.com/", "游戏"),
        ("PlayStation", "PlayStation", "https://www.playstation.com/", "游戏"),
        ("Xbox", "Xbox", "https://www.xbox.com/", "游戏"),
    ]),
    ("read", "Reading", "阅读书籍", [
        ("微信读书", "WeRead", "https://weread.qq.com/", "电子书"),
        ("起点中文网", "Qidian", "https://www.qidian.com/", "网络小说"),
        ("豆瓣读书", "Douban Books", "https://book.douban.com/", "书评"),
        ("Project Gutenberg", "Gutenberg", "https://www.gutenberg.org/", "公版书"),
        ("互联网档案馆", "Internet Archive", "https://archive.org/", "公开档案"),
        ("国家图书馆", "National Library", "https://www.nlc.cn/", "图书馆"),
    ]),
    ("office", "Office", "办公协作", [
        ("腾讯文档", "Tencent Docs", "https://docs.qq.com/", "在线文档"),
        ("飞书", "Feishu", "https://www.feishu.cn/", "协作"),
        ("钉钉", "DingTalk", "https://www.dingtalk.com/", "办公"),
        ("Notion", "Notion", "https://www.notion.com/", "笔记"),
        ("Google 文档", "Google Docs", "https://docs.google.com/", "在线文档"),
        ("石墨文档", "Shimo", "https://shimo.im/", "在线文档"),
    ]),
    ("dev", "Developers", "开发文档", [
        ("GitHub", "GitHub", "https://github.com/", "代码托管"),
        ("GitLab", "GitLab", "https://gitlab.com/", "代码托管"),
        ("npm", "npm", "https://www.npmjs.com/", "JavaScript 包"),
        ("PyPI", "PyPI", "https://pypi.org/", "Python 包"),
        ("Docker Hub", "Docker Hub", "https://hub.docker.com/", "容器镜像"),
        ("Stack Overflow", "Stack Overflow", "https://stackoverflow.com/", "编程问答"),
    ]),
    ("photo", "Photos", "图片壁纸", [
        ("Unsplash", "Unsplash", "https://unsplash.com/", "免费照片"),
        ("Pexels", "Pexels", "https://www.pexels.com/", "免费图片"),
        ("Wallhaven", "Wallhaven", "https://wallhaven.cc/", "壁纸"),
        ("500px", "500px", "https://500px.com/", "摄影"),
        ("Flickr", "Flickr", "https://www.flickr.com/", "摄影"),
    ]),
    ("health", "Health", "健康医疗", [
        ("丁香医生", "DXY", "https://dxy.com/", "医学科普"),
        ("好大夫在线", "Haodf", "https://www.haodf.com/", "在线问诊"),
        ("国家卫健委", "NHC", "https://www.nhc.gov.cn/", "卫生健康"),
        ("WHO", "WHO", "https://www.who.int/", "世界卫生组织"),
        ("WebMD", "WebMD", "https://www.webmd.com/", "健康信息"),
    ]),
    ("sport", "Sports", "体育赛事", [
        ("腾讯体育", "QQ Sports", "https://sports.qq.com/", "体育资讯"),
        ("NBA", "NBA", "https://www.nba.com/", "篮球"),
        ("FIFA", "FIFA", "https://www.fifa.com/", "足球"),
        ("奥运会", "Olympics", "https://olympics.com/", "综合赛事"),
        ("ESPN", "ESPN", "https://www.espn.com/", "体育资讯"),
    ]),
    ("oss", "Open source", "开源工具", [
        ("Gitee", "Gitee", "https://gitee.com/", "代码托管"),
        ("Codeberg", "Codeberg", "https://codeberg.org/", "代码托管"),
        ("SourceForge", "SourceForge", "https://sourceforge.net/", "开源项目"),
        ("GNU", "GNU", "https://www.gnu.org/", "自由软件"),
        ("Apache", "Apache", "https://www.apache.org/", "开源基金会"),
        ("Linux Foundation", "Linux Foundation", "https://www.linuxfoundation.org/", "开源基金会"),
    ]),
    ("os", "Operating systems", "操作系统", [
        ("Ubuntu", "Ubuntu", "https://ubuntu.com/", "Linux 发行版"),
        ("Debian", "Debian", "https://www.debian.org/", "Linux 发行版"),
        ("Fedora", "Fedora", "https://fedoraproject.org/", "Linux 发行版"),
        ("Arch Linux", "Arch Linux", "https://archlinux.org/", "Linux 发行版"),
        ("微软", "Microsoft", "https://www.microsoft.com/", "Windows"),
        ("苹果", "Apple", "https://www.apple.com/", "macOS 与设备"),
    ]),
    ("browser", "Browsers", "浏览器", [
        ("Chrome", "Chrome", "https://www.google.com/chrome/", "浏览器"),
        ("Firefox", "Firefox", "https://www.firefox.com/", "浏览器"),
        ("Edge", "Edge", "https://www.microsoft.com/edge", "浏览器"),
        ("Brave", "Brave", "https://brave.com/", "浏览器"),
        ("Opera", "Opera", "https://www.opera.com/", "浏览器"),
    ]),
    ("cloudplat", "Cloud", "云计算", [
        ("Amazon Web Services", "AWS", "https://aws.amazon.com/", "云服务"),
        ("Microsoft Azure", "Azure", "https://azure.microsoft.com/", "云服务"),
        ("Google Cloud", "Google Cloud", "https://cloud.google.com/", "云服务"),
        ("阿里云", "Alibaba Cloud", "https://www.aliyun.com/", "云服务"),
        ("腾讯云", "Tencent Cloud", "https://cloud.tencent.com/", "云服务"),
        ("华为云", "Huawei Cloud", "https://www.huaweicloud.com/", "云服务"),
    ]),
    ("database", "Databases", "数据库", [
        ("PostgreSQL", "PostgreSQL", "https://www.postgresql.org/", "数据库"),
        ("MySQL", "MySQL", "https://www.mysql.com/", "数据库"),
        ("MongoDB", "MongoDB", "https://www.mongodb.com/", "数据库"),
        ("Redis", "Redis", "https://redis.io/", "数据库"),
        ("SQLite", "SQLite", "https://www.sqlite.org/", "数据库"),
        ("Elastic", "Elastic", "https://www.elastic.co/", "搜索引擎"),
    ]),
    ("aiopen", "AI platforms", "人工智能", [
        ("OpenAI", "OpenAI", "https://openai.com/", "人工智能"),
        ("Hugging Face", "Hugging Face", "https://huggingface.co/", "模型社区"),
        ("Google Gemini", "Gemini", "https://gemini.google.com/", "人工智能"),
        ("Anthropic", "Anthropic", "https://www.anthropic.com/", "人工智能"),
        ("通义", "Qwen", "https://tongyi.aliyun.com/", "人工智能"),
        ("Kimi", "Kimi", "https://kimi.moonshot.cn/", "人工智能"),
    ]),
    ("science", "Science", "科研论文", [
        ("arXiv", "arXiv", "https://arxiv.org/", "预印本"),
        ("PubMed", "PubMed", "https://pubmed.ncbi.nlm.nih.gov/", "医学文献"),
        ("Google Scholar", "Google Scholar", "https://scholar.google.com/", "学术搜索"),
        ("中国知网", "CNKI", "https://www.cnki.net/", "中文学术"),
        ("Semantic Scholar", "Semantic Scholar", "https://www.semanticscholar.org/", "学术搜索"),
        ("OpenAlex", "OpenAlex", "https://openalex.org/", "开放学术"),
    ]),
    ("patent", "IP and standards", "专利标准", [
        ("国家知识产权局", "CNIPA", "https://www.cnipa.gov.cn/", "专利商标"),
        ("WIPO", "WIPO", "https://www.wipo.int/", "知识产权"),
        ("Google Patents", "Google Patents", "https://patents.google.com/", "专利搜索"),
        ("ISO", "ISO", "https://www.iso.org/", "国际标准"),
        ("IETF", "IETF", "https://www.ietf.org/", "互联网标准"),
        ("W3C", "W3C", "https://www.w3.org/", "Web 标准"),
    ]),
    ("stats", "Data", "统计数据", [
        ("国家统计局", "NBS", "https://www.stats.gov.cn/", "统计"),
        ("World Bank", "World Bank", "https://www.worldbank.org/", "全球数据"),
        ("Our World in Data", "Our World in Data", "https://ourworldindata.org/", "公开数据"),
        ("联合国数据", "UNdata", "https://data.un.org/", "国际数据"),
        ("FRED", "FRED", "https://fred.stlouisfed.org/", "经济数据"),
    ]),
    ("security", "Security", "网络安全", [
        ("Let's Encrypt", "Let's Encrypt", "https://letsencrypt.org/", "免费证书"),
        ("VirusTotal", "VirusTotal", "https://www.virustotal.com/", "文件检测"),
        ("Have I Been Pwned", "HIBP", "https://haveibeenpwned.com/", "泄露查询"),
        ("Cloudflare", "Cloudflare", "https://www.cloudflare.com/", "网络服务"),
        ("Mozilla Observatory", "Observatory", "https://observatory.mozilla.org/", "站点安全"),
        ("国家互联网应急中心", "CNCERT", "https://www.cert.org.cn/", "网络安全"),
    ]),
    ("designapp", "Design apps", "设计软件", [
        ("Figma", "Figma", "https://www.figma.com/", "界面设计"),
        ("Canva", "Canva", "https://www.canva.com/", "平面设计"),
        ("Adobe", "Adobe", "https://www.adobe.com/", "设计软件"),
        ("Blender", "Blender", "https://www.blender.org/", "三维软件"),
        ("Penpot", "Penpot", "https://penpot.app/", "开源设计"),
    ]),
    ("lang", "Languages", "语言学习", [
        ("Duolingo", "Duolingo", "https://www.duolingo.com/", "语言学习"),
        ("BBC Learning", "BBC Learning", "https://www.bbc.co.uk/learningenglish", "英语学习"),
        ("多邻国故事", "LingQ", "https://www.lingq.com/", "阅读学语言"),
        ("Forvo", "Forvo", "https://forvo.com/", "发音"),
        ("Tatoeba", "Tatoeba", "https://tatoeba.org/", "例句"),
    ]),
    ("kids", "Education for kids", "基础教育", [
        ("国家中小学智慧教育", "SmartEdu Schools", "https://basic.smartedu.cn/", "中小学课程"),
        ("可汗学院儿童", "Khan Academy Kids", "https://learn.khanacademy.org/khan-academy-kids/", "儿童学习"),
        ("PBS Kids", "PBS Kids", "https://pbskids.org/", "儿童内容"),
        ("Code.org", "Code.org", "https://code.org/", "少儿编程"),
        ("Scratch", "Scratch", "https://scratch.mit.edu/", "少儿编程"),
    ]),
    ("house", "Housing", "房产家居", [
        ("贝壳找房", "Beike", "https://www.ke.com/", "房产"),
        ("链家", "Lianjia", "https://lianjia.com/", "房产"),
        ("安居客", "Anjuke", "https://www.anjuke.com/", "房产"),
        ("住建部", "MOHURD", "https://www.mohurd.gov.cn/", "住房城乡建设"),
        ("IKEA", "IKEA", "https://www.ikea.com/", "家居"),
    ]),
    ("auto", "Cars", "汽车出行", [
        ("汽车之家", "Autohome", "https://www.autohome.com.cn/", "汽车资讯"),
        ("懂车帝", "Dongchedi", "https://www.dongchedi.com/", "汽车资讯"),
        ("特斯拉", "Tesla", "https://www.tesla.com/", "汽车"),
        ("交通运输部", "MOT", "https://www.mot.gov.cn/", "交通运输"),
        ("高德地图", "Amap", "https://www.amap.com/", "地图导航"),
    ]),
    ("food", "Food", "餐饮美食", [
        ("下厨房", "Xiachufang", "https://www.xiachufang.com/", "菜谱"),
        ("大众点评", "Dianping", "https://www.dianping.com/", "本地生活"),
        ("美团", "Meituan", "https://www.meituan.com/", "本地生活"),
        ("饿了么", "Ele.me", "https://www.ele.me/", "外卖"),
        ("Allrecipes", "Allrecipes", "https://www.allrecipes.com/", "菜谱"),
    ]),
    ("baby", "Family", "母婴亲子", [
        ("宝宝树", "Babytree", "https://www.babytree.com/", "母婴"),
        ("国家卫健委妇幼", "NHC", "https://www.nhc.gov.cn/", "妇幼健康"),
        ("AAP", "HealthyChildren", "https://www.healthychildren.org/", "儿童健康"),
        ("UNICEF", "UNICEF", "https://www.unicef.org/", "儿童权益"),
    ]),
    ("farm", "Agriculture", "农业乡村", [
        ("农业农村部", "MARA", "https://www.moa.gov.cn/", "农业"),
        ("中国农村网", "Farmer", "https://www.farmer.com.cn/", "农业资讯"),
        ("FAO", "FAO", "https://www.fao.org/", "粮农组织"),
        ("中国天气农业", "Weather", "https://www.weather.com.cn/", "农业气象"),
    ]),
    ("energy", "Energy", "能源环保", [
        ("国家能源局", "NEA", "https://www.nea.gov.cn/", "能源"),
        ("生态环境部", "MEE", "https://www.mee.gov.cn/", "生态环境"),
        ("IEA", "IEA", "https://www.iea.org/", "国际能源"),
        ("NASA Climate", "NASA Climate", "https://climate.nasa.gov/", "气候"),
        ("UNEP", "UNEP", "https://www.unep.org/", "环境规划署"),
    ]),
    ("culture", "Culture", "文化博物", [
        ("故宫博物院", "Palace Museum", "https://www.dpm.org.cn/", "博物馆"),
        ("大英博物馆", "British Museum", "https://www.britishmuseum.org/", "博物馆"),
        ("大都会艺术博物馆", "The Met", "https://www.metmuseum.org/", "博物馆"),
        ("中国国家博物馆", "National Museum", "https://www.chnmuseum.cn/", "博物馆"),
        ("Google Arts", "Google Arts", "https://artsandculture.google.com/", "艺术"),
    ]),
    ("space", "Space", "天文航天", [
        ("NASA", "NASA", "https://www.nasa.gov/", "航天"),
        ("ESA", "ESA", "https://www.esa.int/", "航天"),
        ("中国载人航天", "CMS", "https://www.cmse.gov.cn/", "航天"),
        ("Stellarium Web", "Stellarium", "https://stellarium-web.org/", "星图"),
        ("Heavens-Above", "Heavens-Above", "https://heavens-above.com/", "卫星"),
    ]),
    ("law", "Law", "法律法规", [
        ("国家法律法规数据库", "NPC Law", "https://flk.npc.gov.cn/", "法律法规"),
        ("最高人民法院", "SPC", "https://www.court.gov.cn/", "法院"),
        ("最高人民检察院", "SPP", "https://www.spp.gov.cn/", "检察"),
        ("司法部", "Ministry of Justice", "https://www.moj.gov.cn/", "司法"),
        ("Cornell LII", "LII", "https://www.law.cornell.edu/", "法律资料"),
    ]),
    ("tax", "Tax and accounting", "财税会计", [
        ("国家税务总局", "Tax", "https://www.chinatax.gov.cn/", "税务"),
        ("财政部", "MOF", "https://www.mof.gov.cn/", "财政"),
        ("中国注册会计师协会", "CICPA", "https://www.cicpa.org.cn/", "会计"),
        ("IFRS", "IFRS", "https://www.ifrs.org/", "国际准则"),
    ]),
    ("hr", "HR", "人力资源", [
        ("人力资源和社会保障部", "MOHRSS", "https://www.mohrss.gov.cn/", "人社"),
        ("LinkedIn", "LinkedIn", "https://www.linkedin.com/", "职业社交"),
        ("Glassdoor", "Glassdoor", "https://www.glassdoor.com/", "雇主评价"),
        ("Levels.fyi", "Levels", "https://www.levels.fyi/", "薪酬参考"),
    ]),
    ("market", "Marketing", "营销广告", [
        ("Google 趋势", "Google Trends", "https://trends.google.com/", "搜索趋势"),
        ("Similarweb", "Similarweb", "https://www.similarweb.com/", "网站分析"),
        ("百度指数", "Baidu Index", "https://index.baidu.com/", "搜索指数"),
        ("Meta 商务", "Meta Business", "https://business.facebook.com/", "广告"),
    ]),
    ("telco", "Telecom", "通信运营商", [
        ("中国移动", "China Mobile", "https://www.10086.cn/", "运营商"),
        ("中国电信", "China Telecom", "https://www.189.cn/", "运营商"),
        ("中国联通", "China Unicom", "https://www.10010.com/", "运营商"),
        ("工信部", "MIIT", "https://www.miit.gov.cn/", "工业和信息化"),
    ]),
    ("hardware", "Hardware", "数码硬件", [
        ("中关村在线", "ZOL", "https://www.zol.com.cn/", "数码资讯"),
        ("什么值得买", "SMZDM", "https://www.smzdm.com/", "消费决策"),
        ("AnandTech", "AnandTech", "https://www.anandtech.com/", "硬件评测"),
        ("GSMArena", "GSMArena", "https://www.gsmarena.com/", "手机参数"),
        ("PassMark", "PassMark", "https://www.passmark.com/", "硬件跑分"),
    ]),
    ("charity", "Public good", "公益慈善", [
        ("中国红十字会", "Red Cross China", "https://www.redcross.org.cn/", "公益"),
        ("红十字国际委员会", "ICRC", "https://www.icrc.org/", "人道"),
        ("联合国", "United Nations", "https://www.un.org/", "国际组织"),
        ("维基媒体", "Wikimedia", "https://www.wikimedia.org/", "知识公益"),
    ]),
    ("world", "World portals", "全球门户", [
        ("Wikipedia", "Wikipedia", "https://www.wikipedia.org/", "多语言百科"),
        ("Internet Archive", "Internet Archive", "https://archive.org/", "全球档案"),
        ("Wikimedia Commons", "Commons", "https://commons.wikimedia.org/", "自由媒体"),
        ("联合国", "United Nations", "https://www.un.org/", "国际组织"),
        ("世界银行", "World Bank", "https://www.worldbank.org/", "全球数据"),
        ("经济合作组织", "OECD", "https://www.oecd.org/", "国际统计"),
    ]),
    ("regions", "Regional media", "地区媒体", [
        ("BBC", "BBC", "https://www.bbc.com/", "英国"),
        ("NPR", "NPR", "https://www.npr.org/", "美国"),
        ("ABC News Australia", "ABC Australia", "https://www.abc.net.au/news", "澳大利亚"),
        ("CBC", "CBC", "https://www.cbc.ca/", "加拿大"),
        ("The Hindu", "The Hindu", "https://www.thehindu.com/", "印度"),
        ("Straits Times", "Straits Times", "https://www.straitstimes.com/", "新加坡"),
        ("Bangkok Post", "Bangkok Post", "https://www.bangkokpost.com/", "泰国"),
        ("Folha", "Folha", "https://www.folha.uol.com.br/", "巴西"),
        ("El País", "El País", "https://elpais.com/", "西班牙"),
        ("Der Spiegel", "Der Spiegel", "https://www.spiegel.de/", "德国"),
    ]),
    ("univ", "Universities", "全球高校", [
        ("MIT", "MIT", "https://www.mit.edu/", "美国"),
        ("Stanford", "Stanford", "https://www.stanford.edu/", "美国"),
        ("Harvard", "Harvard", "https://www.harvard.edu/", "美国"),
        ("Oxford", "Oxford", "https://www.ox.ac.uk/", "英国"),
        ("Cambridge", "Cambridge", "https://www.cam.ac.uk/", "英国"),
        ("ETH Zurich", "ETH", "https://ethz.ch/", "瑞士"),
        ("东京大学", "University of Tokyo", "https://www.u-tokyo.ac.jp/", "日本"),
        ("新加坡国立大学", "NUS", "https://www.nus.edu.sg/", "新加坡"),
        ("多伦多大学", "University of Toronto", "https://www.utoronto.ca/", "加拿大"),
        ("墨尔本大学", "University of Melbourne", "https://www.unimelb.edu.au/", "澳大利亚"),
    ]),
    ("library", "Libraries", "全球图书馆", [
        ("Library of Congress", "Library of Congress", "https://www.loc.gov/", "美国"),
        ("British Library", "British Library", "https://www.bl.uk/", "英国"),
        ("Bibliothèque nationale", "BnF", "https://www.bnf.fr/", "法国"),
        ("Deutsche Nationalbibliothek", "DNB", "https://www.dnb.de/", "德国"),
        ("国立国会图书馆", "NDL", "https://www.ndl.go.jp/", "日本"),
        ("Internet Archive", "Internet Archive", "https://archive.org/", "全球"),
    ]),
    ("maps", "Maps", "全球地图", [
        ("Google Maps", "Google Maps", "https://maps.google.com/", "全球"),
        ("Apple Maps", "Apple Maps", "https://maps.apple.com/", "全球"),
        ("OpenStreetMap", "OpenStreetMap", "https://www.openstreetmap.org/", "全球"),
        ("Mapbox", "Mapbox", "https://www.mapbox.com/", "地图服务"),
        ("Bing Maps", "Bing Maps", "https://www.bing.com/maps", "全球"),
    ]),
    ("weather", "World weather", "全球天气", [
        ("Met Office", "Met Office", "https://www.metoffice.gov.uk/", "英国"),
        ("NOAA", "NOAA", "https://www.noaa.gov/", "美国"),
        ("JMA", "JMA", "https://www.jma.go.jp/", "日本"),
        ("Weather.com", "Weather.com", "https://weather.com/", "全球"),
        ("WMO", "WMO", "https://wmo.int/", "世界气象组织"),
    ]),
    ("transit", "Transit", "全球交通", [
        ("Rome2Rio", "Rome2Rio", "https://www.rome2rio.com/", "跨国路线"),
        ("Kayak", "Kayak", "https://www.kayak.com/", "机票酒店"),
        ("Trainline", "Trainline", "https://www.thetrainline.com/", "欧洲铁路"),
        ("JR East", "JR East", "https://www.jreast.co.jp/", "日本铁路"),
        ("SNCF", "SNCF", "https://www.sncf.com/", "法国铁路"),
        ("Deutsche Bahn", "DB", "https://www.bahn.com/", "德国铁路"),
    ]),
    ("healthw", "World health", "全球卫生", [
        ("WHO", "WHO", "https://www.who.int/", "世界卫生组织"),
        ("CDC", "CDC", "https://www.cdc.gov/", "美国"),
        ("NHS", "NHS", "https://www.nhs.uk/", "英国"),
        ("EMA", "EMA", "https://www.ema.europa.eu/", "欧盟药品"),
        ("Mayo Clinic", "Mayo Clinic", "https://www.mayoclinic.org/", "美国"),
    ]),
    ("devworld", "Global dev", "全球开发", [
        ("MDN", "MDN", "https://developer.mozilla.org/", "Web"),
        ("Go", "Go", "https://go.dev/", "语言"),
        ("Rust", "Rust", "https://www.rust-lang.org/", "语言"),
        ("Kubernetes", "Kubernetes", "https://kubernetes.io/", "编排"),
        ("Python", "Python", "https://www.python.org/", "语言"),
        ("Node.js", "Node.js", "https://nodejs.org/", "运行时"),
    ]),
    ("visa", "Visas", "各国签证", [
        ("美国签证", "US Visas", "https://travel.state.gov/content/travel/en/us-visas.html", "美国"),
        ("英国签证", "UK Visas", "https://www.gov.uk/browse/visas-immigration", "英国"),
        ("申根签证", "Schengen", "https://home-affairs.ec.europa.eu/policies/schengen-borders-and-visa/visa-policy_en", "欧盟"),
        ("法国签证", "France-Visas", "https://france-visas.gouv.fr/", "法国"),
        ("日本签证", "Japan Visa", "https://www.mofa.go.jp/j_info/visit/visa/index.html", "日本"),
        ("加拿大签证", "Canada IRCC", "https://www.canada.ca/en/immigration-refugees-citizenship.html", "加拿大"),
        ("澳大利亚签证", "Australia Home Affairs", "https://immi.homeaffairs.gov.au/", "澳大利亚"),
        ("新西兰签证", "New Zealand", "https://www.immigration.govt.nz/", "新西兰"),
        ("新加坡签证", "Singapore ICA", "https://www.ica.gov.sg/", "新加坡"),
        ("韩国签证", "Korea Visa", "https://www.visa.go.kr/", "韩国"),
        ("中国签证", "China Visa", "https://cs.mfa.gov.cn/", "中国"),
        ("泰国签证", "Thailand e-Visa", "https://www.thaievisa.go.th/", "泰国"),
        ("阿联酋签证", "UAE ICP", "https://icp.gov.ae/", "阿联酋"),
        ("印度签证", "India e-Visa", "https://indianvisaonline.gov.in/", "印度"),
    ]),
    ("events", "Major events", "全球大事", [
        ("路透", "Reuters", "https://www.reuters.com/", "国际突发"),
        ("美联社", "AP", "https://apnews.com/", "国际突发"),
        ("联合国新闻", "UN News", "https://news.un.org/", "国际组织"),
        ("ReliefWeb", "ReliefWeb", "https://reliefweb.int/", "人道危机"),
        ("国际危机组织", "Crisis Group", "https://www.crisisgroup.org/", "冲突与风险"),
        ("WHO 突发卫生", "WHO Emergencies", "https://www.who.int/emergencies", "卫生事件"),
        ("美国地质调查局", "USGS", "https://www.usgs.gov/natural-hazards/earthquake-hazards", "地震"),
        ("全球灾害警报", "GDACS", "https://www.gdacs.org/", "灾害警报"),
        ("FEMA", "FEMA", "https://www.fema.gov/", "美国灾害"),
        ("维基当前事件", "Wikipedia Current", "https://en.wikipedia.org/wiki/Portal:Current_events", "事件汇编"),
        ("外交关系协会", "CFR", "https://www.cfr.org/", "国际事务"),
        ("奥运会", "Olympics", "https://olympics.com/", "大型赛事"),
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
        category.sort = index
        for title_zh, title_en, url, desc in items:
            key = norm_url(url)
            if db.scalar(select(Link.id).where(Link.category_id == category.id, Link.norm_url == key)):
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


WORLD = {
    "ai": ("global-ai", "Global AI", "全球AI", [
        ("OpenAI", "OpenAI", "https://openai.com/", "美国"),
        ("Anthropic", "Anthropic", "https://www.anthropic.com/", "美国"),
        ("Google DeepMind", "DeepMind", "https://deepmind.google/", "英国"),
        ("Mistral", "Mistral", "https://mistral.ai/", "法国"),
        ("Hugging Face", "Hugging Face", "https://huggingface.co/", "全球模型"),
        ("Perplexity", "Perplexity", "https://www.perplexity.ai/", "美国"),
        ("Midjourney", "Midjourney", "https://www.midjourney.com/", "美国"),
        ("Stability AI", "Stability", "https://stability.ai/", "英国"),
        ("ElevenLabs", "ElevenLabs", "https://elevenlabs.io/", "美国"),
        ("Cohere", "Cohere", "https://cohere.com/", "加拿大"),
    ]),
    "cross-border": ("global-trade", "Global commerce", "全球电商", [
        ("Amazon", "Amazon", "https://www.amazon.com/", "美国"),
        ("Amazon UK", "Amazon UK", "https://www.amazon.co.uk/", "英国"),
        ("Amazon Japan", "Amazon Japan", "https://www.amazon.co.jp/", "日本"),
        ("Amazon Germany", "Amazon DE", "https://www.amazon.de/", "德国"),
        ("Shopify", "Shopify", "https://www.shopify.com/", "加拿大"),
        ("eBay", "eBay", "https://www.ebay.com/", "全球"),
        ("Etsy", "Etsy", "https://www.etsy.com/", "美国"),
        ("Walmart", "Walmart", "https://www.walmart.com/", "美国"),
        ("Allegro", "Allegro", "https://allegro.pl/", "波兰"),
        ("Otto", "Otto", "https://www.otto.de/", "德国"),
        ("PayPal", "PayPal", "https://www.paypal.com/", "支付"),
        ("Wise", "Wise", "https://wise.com/", "跨境汇款"),
    ]),
    "media": ("global-night", "Global night media", "全球媒体", [
        ("IMDb", "IMDb", "https://www.imdb.com/", "影视资料"),
        ("JustWatch", "JustWatch", "https://www.justwatch.com/", "正版观看入口"),
        ("Netflix", "Netflix", "https://www.netflix.com/", "全球"),
        ("Letterboxd", "Letterboxd", "https://letterboxd.com/", "影评"),
        ("Crunchyroll", "Crunchyroll", "https://www.crunchyroll.com/", "日本动画"),
    ]),
    "telegram": ("global-tg", "Global Telegram", "全球电报", [
        ("Telegram", "Telegram", "https://telegram.org/", "官方"),
        ("Telegram Blog", "Telegram Blog", "https://telegram.org/blog", "官方"),
        ("Telegram API", "Telegram API", "https://core.telegram.org/", "开发文档"),
        ("Durov", "Durov", "https://t.me/durov", "创始人频道"),
        ("Telegram News", "Telegram News", "https://t.me/telegram", "官方频道"),
    ]),
}


def ensure_world(db: Session) -> None:
    import random

    for tab_slug, (slug, en, zh, items) in WORLD.items():
        tab = db.scalar(select(Tab).where(Tab.slug == tab_slug))
        if not tab:
            continue
        category = db.scalar(select(Category).where(Category.tab_id == tab.id, Category.slug == slug))
        if not category:
            category = Category(tab_id=tab.id, slug=slug, title_en=en, title_zh=zh, sort=0, visible=True)
            db.add(category)
            db.flush()
        for title_zh, title_en, url, desc in items:
            key = norm_url(url)
            if db.scalar(select(Link.id).where(Link.category_id == category.id, Link.norm_url == key)):
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
        ensure_world(db)
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
            title_en="About NEXA",
            title_zh="关于我们",
            body_en="NEXA is a bilingual directory for finding AI tools, cross-border tools, media sites, and public Telegram channels in one place.\n\nWhat you can find\nSections group AI chat, writing, image tools, cross-border selling, and media sites. Each entry is an outbound link. The side list jumps straight to a category.\n\nNews and rankings\nThe home page keeps the last 24 hours of Chinese and English stories in the same topics. Older items drop off on the next sync. GitHub growth and total-star boards sit beside the news and rank by count.\n\nPoints and levels\nSearch and browse without an account. Register to submit a link. Each approved link adds points, and points raise your level. Higher levels unlock benefits that keep being updated. A level, once reached, stays with the account.",
            body_zh="NEXA 是中英双语导航站，把 AI 工具、跨境工具、媒体网站和公开的 Telegram 频道集中在一个页面里查找。\n\n能找到什么\n栏目按 AI 对话、写作、图像、跨境和媒体分组。每条都是可打开的外链，左侧分类可以直接跳到对应内容。\n\n资讯和排行\n综合资讯保留最近 24 小时的中文和英文来源，同一话题放在一起。过期条目会在下一次同步时清掉。旁边是 GitHub 增量和总星标两块排行，按数量从高到低。\n\n积分与升级\n不注册也可以搜索和浏览。注册后可以提交链接，通过审核的链接会计入积分，积分用来升级。升级后可以畅享对应福利，福利会长期更新。已经达到的等级永久有效。",
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
