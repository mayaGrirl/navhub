import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings


def _client():
    kwargs = {"timeout": 12, "follow_redirects": True, "headers": {"User-Agent": "NavhubBot/1.0"}}
    if settings.proxy_pool_url:
        try:
            response = httpx.get(f"{settings.proxy_pool_url.rstrip('/')}/acquire", timeout=3)
            if response.status_code == 200 and response.json().get("proxy"):
                kwargs["proxy"] = response.json()["proxy"]
        except httpx.HTTPError:
            pass
    return httpx.Client(**kwargs)


def _public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must be http or https")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 80)}
    except socket.gaierror as exc:
        raise ValueError("could not resolve host") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("that address is not allowed")
    return url


def fetch_meta(url: str) -> dict:
    url = _public_url(url)
    with _client() as client:
        response = client.get(url)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    description = ""
    desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if desc and desc.get("content"):
        description = desc["content"].strip()
    image = ""
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        image = urljoin(url, og["content"])
    return {"title": title[:180], "description": description[:500], "logo_url": image[:500], "url": url}
