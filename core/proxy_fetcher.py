# Credits: TSun × Kittens — Proxy Fetcher Module
"""
core/proxy_fetcher.py
~~~~~~~~~~~~~~~~~~~~~
Auto-fetches free HTTP proxies from public sources,
tests them against Garena + Free Fire servers,
and saves working ones to proxies.txt.

مصادر مضافة:
  - ProxyScrape API (v2 + v3)
  - GeoNode API (JSON)
  - 10+ GitHub lists
  
فحص مزدوج:
  - https://100067.connect.garena.com   (Garena OAuth)
  - https://loginbp.ggblueshark.com     (Free Fire Login)
"""

from __future__ import annotations

import os
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import config.settings as settings

PROXY_FILE    = os.path.join(settings.PROJECT_ROOT, "proxies.txt")
TEST_TIMEOUT  = 7
FETCH_TIMEOUT = 10

# سيرفرات الفحص — يكفي أن ينجح مع أي منها
_TEST_URLS = [
    "https://100067.connect.garena.com",
    "https://loginbp.ggblueshark.com",
]

# مصادر بروكسيات مجانية — 14 مصدر
_SOURCES = [
    # ProxyScrape API — أكبر مصدر
    "https://api.proxyscrape.com/v3/free-proxy-list/get?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all&simplified=true",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=8000&country=all&ssl=all&anonymity=all",
    # GeoNode API — JSON format
    "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=http",
    # GitHub lists — تُحدَّث يومياً
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
    "https://raw.githubusercontent.com/UptimerBot/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
]

_fetch_lock = threading.Lock()


def _fetch_from_source(url: str) -> list[str]:
    """تجلب بروكسيات خام من مصدر واحد — تدعم JSON (GeoNode) ونص عادي."""
    try:
        resp = requests.get(
            url, timeout=FETCH_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
            verify=False,
        )
        if resp.status_code != 200:
            return []

        # GeoNode يرسل JSON
        if "geonode.com" in url:
            try:
                data = resp.json()
                return [
                    f"{e['ip']}:{e['port']}"
                    for e in data.get("data", [])
                    if e.get("ip") and str(e.get("port", "")).isdigit()
                ]
            except Exception:
                pass

        # نص عادي — سطر بسطر
        lines = []
        for line in resp.text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # تنظيف http:// أو https://
            for pfx in ("https://", "http://"):
                if line.startswith(pfx):
                    line = line[len(pfx):]
                    break
            # أخذ أول جزء قبل مسافة
            line = line.split()[0] if " " in line else line
            parts = line.split(":")
            if len(parts) == 2 and parts[1].isdigit():
                port = int(parts[1])
                if 1 <= port <= 65535:
                    lines.append(f"{parts[0]}:{port}")
        return lines
    except Exception:
        return []


def _test_proxy(proxy_str: str) -> bool:
    """
    يفحص البروكسي ضد سيرفرات Free Fire الحقيقية.
    يمرر إذا نجح مع أي سيرفر.
    """
    proxies = {"http": f"http://{proxy_str}", "https": f"http://{proxy_str}"}
    for url in _TEST_URLS:
        try:
            resp = requests.get(
                url,
                proxies=proxies,
                timeout=TEST_TIMEOUT,
                verify=False,
                headers={"User-Agent": "TSun-Proxy-Checker/1.0"},
                allow_redirects=True,
            )
            if resp.status_code != 407:
                return True
        except Exception:
            continue
    return False


def fetch_and_test_proxies(
    max_test: int = 500,
    max_alive: int = 80,
    on_progress: Callable[[int, int, int], None] | None = None,
) -> tuple[int, int]:
    """
    يجلب بروكسيات من 14 مصدر، يفحصها على سيرفر Free Fire،
    ويحفظ الشغالة في proxies.txt.

    Returns: (alive_count, total_tested)
    """
    # خطوة 1: جلب من كل المصادر بالتوازي
    all_raw: list[str] = []
    seen: set[str] = set()

    with ThreadPoolExecutor(max_workers=len(_SOURCES)) as ex:
        futures = {ex.submit(_fetch_from_source, url): url for url in _SOURCES}
        for fut in as_completed(futures):
            for p in fut.result():
                if p not in seen:
                    seen.add(p)
                    all_raw.append(p)

    # خلط عشوائي لتنويع المصادر
    random.shuffle(all_raw)
    to_test = all_raw[:max_test]

    if not to_test:
        return 0, 0

    # خطوة 2: فحص موازي (60 thread)
    alive: list[str] = []
    tested = 0
    workers = min(60, len(to_test))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_test_proxy, p): p for p in to_test}
        for fut in as_completed(futures):
            proxy_str = futures[fut]
            tested += 1
            is_ok = fut.result()
            if is_ok:
                alive.append(proxy_str)
            if on_progress:
                on_progress(tested, len(to_test), len(alive))
            if len(alive) >= max_alive:
                ex.shutdown(wait=False, cancel_futures=True)
                break

    # خطوة 3: احفظ الشغالة في proxies.txt (أضف للموجودة بدون تكرار)
    with _fetch_lock:
        existing: set[str] = set()
        if os.path.exists(PROXY_FILE):
            with open(PROXY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        existing.add(line)

        new_proxies = [p for p in alive if p not in existing]
        if new_proxies:
            with open(PROXY_FILE, "a", encoding="utf-8") as f:
                for p in new_proxies:
                    f.write(p + "\n")

    return len(alive), tested


def load_proxies_from_text(text: str) -> int:
    """
    يضيف بروكسيات من نص (كل سطر = بروكسي) إلى proxies.txt.
    Returns: عدد البروكسيات المضافة.
    """
    added = 0
    with _fetch_lock:
        existing: set[str] = set()
        if os.path.exists(PROXY_FILE):
            with open(PROXY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        existing.add(line)

        new_lines: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for pfx in ("https://", "http://"):
                if line.startswith(pfx):
                    line = line[len(pfx):]
                    break
            parts = line.split(":")
            if len(parts) == 2 and parts[1].isdigit():
                try:
                    port = int(parts[1])
                    if 1 <= port <= 65535 and line not in existing:
                        new_lines.append(line)
                        existing.add(line)
                        added += 1
                except ValueError:
                    pass

        if new_lines:
            with open(PROXY_FILE, "a", encoding="utf-8") as f:
                for p in new_lines:
                    f.write(p + "\n")

    return added


def clear_proxies() -> int:
    """يمسح كل البروكسيات من proxies.txt. Returns عدد البروكسيات المحذوفة."""
    with _fetch_lock:
        count = 0
        if os.path.exists(PROXY_FILE):
            with open(PROXY_FILE, "r", encoding="utf-8") as f:
                count = sum(1 for l in f if l.strip() and not l.strip().startswith("#"))
            open(PROXY_FILE, "w").close()
    return count


def count_proxies() -> int:
    """يعد البروكسيات الموجودة في proxies.txt."""
    if not os.path.exists(PROXY_FILE):
        return 0
    with open(PROXY_FILE, "r", encoding="utf-8") as f:
        return sum(1 for l in f if l.strip() and not l.strip().startswith("#"))
