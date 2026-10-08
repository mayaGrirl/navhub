"""站内视频播放器的直链解析。

只处理"本身就公开、可直接播放"的地址：
- 用户给的地址本身就是 .mp4/.webm/.ogg/.m3u8/.mpd 等直链；
- 或者给的是网页，页面里带有公开的 <video>/<source>/og:video 直链。

明确不做：不调用任何第三方会员解析接口、不破解付费内容、不做 iframe 嵌入。
网络请求复用 crawl.py 的 _public_url 做 SSRF 防护（拒绝内网/环回/保留 IP）。
"""

from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.crawl import BROWSER, _public_url


# 可被 <video> 直接播放，或可被 hls.js / dash.js 播放的后缀
DIRECT_EXT = {
    ".mp4": "mp4",
    ".m4v": "mp4",
    ".webm": "webm",
    ".ogv": "ogg",
    ".ogg": "ogg",
    ".mov": "mp4",
    ".m3u8": "hls",
    ".flv": "flv",
    ".mpd": "dash",
}

MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5


class ResolveError(ValueError):
    """用户可见的解析失败原因（错误码，由前端翻译）。"""


def _ext_kind(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext, kind in DIRECT_EXT.items():
        if path.endswith(ext):
            return kind
    return ""


def _looks_direct(url: str) -> str:
    """地址本身就是直链时，返回其类型，否则空串。"""
    return _ext_kind(url)


def _pick_from_html(base_url: str, html: str) -> tuple[str, str, str]:
    """从网页里挑一个公开直链。返回 (直链, 类型, 标题)。挑不到抛 ResolveError。"""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = og_title["content"].strip() or title

    candidates: list[str] = []

    # 1) Open Graph / Twitter 视频直链
    for attrs in (
        {"property": "og:video:secure_url"},
        {"property": "og:video:url"},
        {"property": "og:video"},
        {"name": "twitter:player:stream"},
    ):
        node = soup.find("meta", attrs=attrs)
        if node and node.get("content"):
            candidates.append(node["content"].strip())

    # 2) <video src> 与 <video><source>
    for video in soup.find_all("video"):
        if video.get("src"):
            candidates.append(video["src"].strip())
        for source in video.find_all("source"):
            if source.get("src"):
                candidates.append(source["src"].strip())

    # 3) <source> 独立出现
    for source in soup.find_all("source"):
        if source.get("src"):
            candidates.append(source["src"].strip())

    for raw in candidates:
        if not raw:
            continue
        absolute = urljoin(base_url, raw)
        kind = _ext_kind(absolute)
        if not kind and absolute.lower().startswith(("http://", "https://")):
            # 没有可识别后缀但确实带有视频扩展名/标志才兜底为 mp4，避免误判普通链接
            lowered = absolute.lower()
            if any(token in lowered for token in (".mp4", ".m3u8", ".flv", "mime=video", "format=mp4")):
                kind = "mp4"
        if not kind:
            continue
        # 提取到的直链也要是公网地址，和"只播公开直链"的承诺一致
        try:
            _public_url(absolute)
        except ValueError:
            continue
        return absolute, kind, title

    raise ResolveError("no_direct")


def _fetch_safe(start_url: str) -> httpx.Response:
    """抓取网页，手动逐跳跟随重定向，每一跳都重新做公网校验，防止重定向绕过 SSRF。

    禁用 httpx 自动重定向（follow_redirects=False），自己处理 3xx 的 Location，
    对每个目标地址都调用 _public_url。失败抛 ResolveError。
    """
    current = start_url
    try:
        with httpx.Client(timeout=10, follow_redirects=False, headers=BROWSER) as client:
            for _ in range(MAX_REDIRECTS + 1):
                try:
                    safe = _public_url(current)
                except ValueError as exc:
                    raise ResolveError("blocked") from exc
                response = client.get(safe)
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ResolveError("unreachable")
                    current = urljoin(str(response.url), location)
                    continue
                return response
    except httpx.HTTPError as exc:
        raise ResolveError("unreachable") from exc
    raise ResolveError("unreachable")


def resolve_video(url: str) -> dict:
    """解析用户地址，返回 {url, kind, title}。失败抛 ResolveError。"""
    raw = (url or "").strip()
    if not raw:
        raise ResolveError("empty")
    if not raw.lower().startswith(("http://", "https://")):
        raw = "https://" + raw

    try:
        safe = _public_url(raw)
    except ValueError as exc:
        raise ResolveError("blocked") from exc

    # 地址本身就是直链：直接返回，不再抓取（已通过公网校验）
    direct = _looks_direct(safe)
    if direct:
        return {"url": safe, "kind": direct, "title": ""}

    # 否则按网页抓取（逐跳校验），从中提取公开直链
    response = _fetch_safe(safe)

    if response.status_code >= 400:
        raise ResolveError("unreachable")

    content_type = (response.headers.get("content-type") or "").lower()
    final_url = str(response.url)

    # 跳转后落到了直链
    direct = _ext_kind(final_url)
    if direct:
        return {"url": final_url, "kind": direct, "title": ""}

    # 响应本身就是视频流
    if content_type.startswith("video/"):
        return {"url": final_url, "kind": "mp4", "title": ""}
    if "mpegurl" in content_type:
        return {"url": final_url, "kind": "hls", "title": ""}
    if "dash+xml" in content_type:
        return {"url": final_url, "kind": "dash", "title": ""}

    if "html" not in content_type and "xml" not in content_type and content_type:
        raise ResolveError("no_direct")

    html = response.text or ""
    if len(html) > MAX_HTML_BYTES:
        html = html[:MAX_HTML_BYTES]
    picked_url, picked_kind, picked_title = _pick_from_html(final_url, html)
    return {"url": picked_url, "kind": picked_kind, "title": picked_title}
