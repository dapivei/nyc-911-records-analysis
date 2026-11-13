"""Polite downloading: one request per second, cached pages, robots.txt, retries.

    get_page(url)          -> HTML text (from cache if already downloaded), or None
    download(url, path)    -> True if the file is now on disk
"""
import gzip
import hashlib
import time
import requests
import config

from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse


session = requests.Session()
session.headers["User-Agent"] = config.USER_AGENT
_last_request = {}
_robots = {}


def _wait(host):
    elapsed = time.monotonic() - _last_request.get(host, 0)
    if elapsed < config.SECONDS_BETWEEN_REQUESTS:
        time.sleep(config.SECONDS_BETWEEN_REQUESTS - elapsed)
    _last_request[host] = time.monotonic()


def _allowed(url):
    host = urlparse(url).netloc
    if host not in _robots:
        rp = robotparser.RobotFileParser()
        try:
            r = session.get(f"{urlparse(url).scheme}://{host}/robots.txt", timeout=30)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse(["User-agent: *", "Disallow: /search", "Disallow: /ask"])
        _robots[host] = rp
    return _robots[host].can_fetch(config.USER_AGENT, url)


def _request(url, **kwargs):
    """GET with retries; waits longer after 429/5xx errors."""
    host = urlparse(url).netloc
    for attempt in range(5):
        _wait(host)
        try:
            r = session.get(url, timeout=60, **kwargs)
        except requests.RequestException as e:
            print(f"  network error ({e}), retrying...")
            time.sleep(5 * 2 ** attempt)
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(float(r.headers.get("Retry-After") or 5 * 2 ** attempt))
            continue
        return r
    print(f"  giving up on {url}")
    return None


def _cache_file(url):
    h = hashlib.sha1(url.encode()).hexdigest()
    return config.HTML_CACHE / h[:2] / f"{h}.html.gz"


def get_page(url):
    url = urljoin(config.SITE, url)
    cached = _cache_file(url)
    if cached.exists():
        return gzip.decompress(cached.read_bytes()).decode("utf-8")
    if not _allowed(url):
        return None
    r = _request(url)
    if r is None or r.status_code != 200:
        return None
    if "charset" not in r.headers.get("Content-Type", "").lower():
        r.encoding = "utf-8"
    html = r.text
    if "turnstile" in html[:5000].lower() or "challenge-platform" in html[:5000].lower():
        raise RuntimeError(f"{url} asked for a human check. Don't bypass it: slow down or use the browser.")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(gzip.compress(html.encode("utf-8")))
    return html


def download(url, path: Path):
    if path.exists():
        return True
    if not _allowed(url):
        return False
    r = _request(url, stream=True)
    if r is None or r.status_code != 200 or "text/html" in r.headers.get("Content-Type", ""):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
    tmp.replace(path)
    return True
