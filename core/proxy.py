# Credits: TSun × Kittens
"""
core/proxy.py
~~~~~~~~~~~~~
نظام البروكسي الذكي:
  - بروكسي واحد شغّال يستخدمه كل الحسابات
  - لما يموت → يتبدّل فوراً للتالي تلقائياً
  - خلفياً يجلب من الإنترنت (ProxyScrape / GeoNode / ProxyNova / GitHub)
    ويفحص الناتج على سيرفر Free Fire مباشرةً
  - لا يُستخدم أي بروكسي لم يجتز الفحص على اللعبة
"""

from __future__ import annotations

import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import config.settings as settings


# ── ثوابت ───────────────────────────────────────────────────────────────────

PROXY_FILE         = os.path.join(settings.PROJECT_ROOT, "proxies.txt")
OFFLINE_PROXY_FILE = os.path.join(settings.PROJECT_ROOT, "offline_proxies.txt")

# سيرفرات الفحص — يمرّ البروكسي لو نجح مع أي منها
_FF_TEST_URLS = [
    "https://100067.connect.garena.com",
    "https://loginbp.ggblueshark.com",
]
PROXY_TEST_URL     = _FF_TEST_URLS[0]
PROXY_TEST_TIMEOUT = 7
FETCH_TIMEOUT      = 10

# مصادر الجلب التلقائي من الإنترنت
_AUTO_SOURCES = [
    "https://api.proxyscrape.com/v3/free-proxy-list/get?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all&simplified=true",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=8000&country=all&ssl=all&anonymity=all",
    "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=http",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
    "https://raw.githubusercontent.com/UptimerBot/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
]

# لما الـ queue تنزل عن هذا الرقم يبدأ refill تلقائياً
_QUEUE_TARGET = 30
_REFILL_LOW   = 6


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProxyEntry:
    """بروكسي موحّد يُمرَّر لـ requests."""
    url:    str
    label:  str
    source: str

    def as_requests_proxies(self) -> dict[str, str]:
        return {"http": self.url, "https": self.url}


@dataclass(frozen=True)
class ProxyCheckResult:
    proxy:    ProxyEntry
    is_alive: bool
    message:  str
    elapsed:  float


@dataclass(frozen=True)
class ProxyCheckSummary:
    alive:         list[ProxyCheckResult]
    dead:          list[ProxyCheckResult]
    invalid_lines: list[str]
    proxy_file:    str
    offline_file:  str


# ── حالة الـ pool ─────────────────────────────────────────────────────────────

_LOCK = threading.Lock()

_ACTIVE_PROXY: ProxyEntry | None = None  # البروكسي الوحيد الشغّال
_READY_QUEUE:  list[ProxyEntry]  = []    # بروكسيات جاهزة ومفحوصة
_REFILL_RUNNING                  = False

# للتوافق الداخلي
_PROXIES:       list[ProxyEntry] | None = None
_INVALID_LINES: list[str]               = []


# ── جلب خام ──────────────────────────────────────────────────────────────────

def _fetch_raw(url: str) -> list[str]:
    """يجلب بروكسيات خام (ip:port) من مصدر واحد."""
    try:
        resp = requests.get(
            url, timeout=FETCH_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
            verify=False,
        )
        if resp.status_code != 200:
            return []

        # GeoNode → JSON
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

        lines = []
        for line in resp.text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for pfx in ("https://", "http://"):
                if line.startswith(pfx):
                    line = line[len(pfx):]
                    break
            line = line.split()[0] if " " in line else line
            parts = line.split(":")
            if len(parts) == 2 and parts[1].isdigit():
                try:
                    if 1 <= int(parts[1]) <= 65535:
                        lines.append(line)
                except ValueError:
                    pass
        return lines
    except Exception:
        return []


# ── فحص على FF ───────────────────────────────────────────────────────────────

def _test_on_ff(proxy_str: str) -> bool:
    """True = البروكسي شغّال على سيرفر Free Fire."""
    px = {"http": f"http://{proxy_str}", "https": f"http://{proxy_str}"}
    for url in _FF_TEST_URLS:
        try:
            r = requests.get(
                url, proxies=px,
                timeout=PROXY_TEST_TIMEOUT,
                verify=False,
                headers={"User-Agent": "TSun-Proxy-Checker/1.0"},
                allow_redirects=True,
            )
            if r.status_code != 407:
                return True
        except Exception:
            continue
    return False


def _make_entry(proxy_str: str) -> ProxyEntry:
    return ProxyEntry(
        url=f"http://{proxy_str}",
        label=proxy_str,
        source=proxy_str,
    )


# ── Background refill ─────────────────────────────────────────────────────────

def _trigger_refill() -> None:
    """يطلق thread الجلب في الخلفية إذا لم يكن يعمل."""
    global _REFILL_RUNNING
    with _LOCK:
        if _REFILL_RUNNING:
            return
        if len(_READY_QUEUE) >= _REFILL_LOW and _ACTIVE_PROXY is not None:
            return
        _REFILL_RUNNING = True
    threading.Thread(target=_bg_refill, daemon=True, name="ProxyRefill").start()


def _bg_refill() -> None:
    """
    1- يجلب من 14 مصدر بالتوازي
    2- يفحص عشوائياً على FF
    3- يضيف الشغالة لـ _READY_QUEUE
    4- يُفعّل _ACTIVE_PROXY فوراً لو ما في واحد
    """
    global _REFILL_RUNNING, _ACTIVE_PROXY, _READY_QUEUE

    try:
        # جلب موازي
        all_raw: list[str] = []
        seen:    set[str]  = set()
        with ThreadPoolExecutor(max_workers=len(_AUTO_SOURCES)) as ex:
            futs = {ex.submit(_fetch_raw, u): u for u in _AUTO_SOURCES}
            for f in as_completed(futs):
                for p in f.result():
                    if p not in seen:
                        seen.add(p)
                        all_raw.append(p)

        random.shuffle(all_raw)

        # كم نحتاج؟
        with _LOCK:
            have = len(_READY_QUEUE) + (1 if _ACTIVE_PROXY else 0)
        need = max(_QUEUE_TARGET - have, 0)
        if need == 0:
            return

        # فحص موازي على FF
        found: list[str] = []
        batch   = all_raw[:600]
        workers = min(60, len(batch))

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs2 = {ex.submit(_test_on_ff, p): p for p in batch}
            for f in as_completed(futs2):
                p = futs2[f]
                try:
                    ok = f.result()
                except Exception:
                    ok = False
                if ok:
                    found.append(p)
                if len(found) >= need:
                    ex.shutdown(wait=False, cancel_futures=True)
                    break

        if not found:
            return

        new_entries = [_make_entry(p) for p in found]

        with _LOCK:
            ex_src = {e.source for e in _READY_QUEUE}
            if _ACTIVE_PROXY:
                ex_src.add(_ACTIVE_PROXY.source)
            for e in new_entries:
                if e.source not in ex_src:
                    _READY_QUEUE.append(e)
                    ex_src.add(e.source)
            # فعّل واحداً فوراً لو ما في active
            if _ACTIVE_PROXY is None and _READY_QUEUE:
                _ACTIVE_PROXY = _READY_QUEUE.pop(0)

        _save_to_file(found)

    finally:
        with _LOCK:
            _REFILL_RUNNING = False


def _save_to_file(proxies: list[str]) -> None:
    try:
        existing: set[str] = set()
        if os.path.exists(PROXY_FILE):
            with open(PROXY_FILE, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        existing.add(line)
        new = [p for p in proxies if p not in existing]
        if new:
            with open(PROXY_FILE, "a", encoding="utf-8") as fh:
                for p in new:
                    fh.write(p + "\n")
    except Exception:
        pass


# ── API رئيسي ─────────────────────────────────────────────────────────────────

def get_active_proxy() -> ProxyEntry | None:
    """
    البروكسي الشغّال الحالي — كل الحسابات تستخدم نفسه.
    لو ما في بروكسي جاهز → يطلق refill ويرجع None (اتصال مباشر مؤقتاً).
    """
    global _ACTIVE_PROXY, _READY_QUEUE, _PROXIES

    with _LOCK:
        if _ACTIVE_PROXY is not None:
            return _ACTIVE_PROXY
        if _READY_QUEUE:
            _ACTIVE_PROXY = _READY_QUEUE.pop(0)
            return _ACTIVE_PROXY
        # fallback: جرّب proxies.txt
        if _PROXIES is None:
            _PROXIES, _ = _read_proxy_file_details()
        if _PROXIES:
            _ACTIVE_PROXY = _PROXIES.pop(0)
            return _ACTIVE_PROXY

    _trigger_refill()
    return None


def get_next_proxy() -> ProxyEntry | None:
    """توافق مع الكود القديم — نفس get_active_proxy."""
    return get_active_proxy()


def mark_proxy_dead(proxy: ProxyEntry | None) -> None:
    """
    البروكسي مات → بدّله للتالي فوراً، وابدأ refill لو الـ queue فاضية.
    يُستدعى من api.py عند 429 أو connection error.
    """
    global _ACTIVE_PROXY, _READY_QUEUE

    if proxy is None:
        return

    with _LOCK:
        if _ACTIVE_PROXY and _ACTIVE_PROXY.source == proxy.source:
            _ACTIVE_PROXY = _READY_QUEUE.pop(0) if _READY_QUEUE else None
        _READY_QUEUE = [e for e in _READY_QUEUE if e.source != proxy.source]
        q = len(_READY_QUEUE)

    if q < _REFILL_LOW:
        _trigger_refill()


def get_proxy_stats() -> tuple[int, int, str]:
    """(عدد البروكسيات الجاهزة, 0, PROXY_FILE)"""
    with _LOCK:
        total = len(_READY_QUEUE) + (1 if _ACTIVE_PROXY else 0)
    return total, 0, PROXY_FILE


def refresh_proxy_pool() -> tuple[int, int, str]:
    """يعيد تحميل proxies.txt ويضيف للـ queue، ثم يطلق internet refill."""
    global _ACTIVE_PROXY, _READY_QUEUE, _INVALID_LINES

    with _LOCK:
        entries, inv = _read_proxy_file_details()
        _INVALID_LINES = inv
        ex_src = {e.source for e in _READY_QUEUE}
        if _ACTIVE_PROXY:
            ex_src.add(_ACTIVE_PROXY.source)
        for e in entries:
            if e.source not in ex_src:
                _READY_QUEUE.append(e)
                ex_src.add(e.source)
        if _ACTIVE_PROXY is None and _READY_QUEUE:
            _ACTIVE_PROXY = _READY_QUEUE.pop(0)
        total = len(_READY_QUEUE) + (1 if _ACTIVE_PROXY else 0)

    _trigger_refill()
    return total, len(inv), PROXY_FILE


# ── تحليل proxies.txt ─────────────────────────────────────────────────────────

def _clean_proxy_value(v: str) -> str:
    v = v.strip()
    while v.endswith(","):
        v = v[:-1].strip()
    return v


def _is_valid_host_port(host: str, port: str) -> bool:
    if not host or not port.isdigit():
        return False
    return 1 <= int(port) <= 65535


def _build_proxy(scheme: str, host: str, port: str, source: str,
                 username: str | None = None, password: str | None = None) -> ProxyEntry | None:
    if not _is_valid_host_port(host, port):
        return None
    if username is None:
        return ProxyEntry(url=f"{scheme}://{host}:{port}", label=f"{host}:{port}", source=source)
    if not username or not password:
        return None
    u = quote(username, safe="")
    p = quote(password, safe="")
    return ProxyEntry(url=f"{scheme}://{u}:{p}@{host}:{port}", label=f"{host}:{port}", source=source)


def _parse_proxy_value(raw: str) -> ProxyEntry | None:
    source = _clean_proxy_value(raw)
    if not source or source.startswith("#"):
        return None
    scheme, body = "http", source
    if "://" in source:
        s, b = source.split("://", 1)
        s = s.lower()
        if s not in ("http", "https") or not b:
            return None
        scheme, body = s, b
    if "@" in body:
        left, right = body.rsplit("@", 1)
        rp = right.split(":")
        if len(rp) == 2 and _is_valid_host_port(rp[0], rp[1]):
            up = left.split(":", 1)
            if len(up) == 2:
                return _build_proxy(scheme, rp[0], rp[1], source, up[0], up[1])
        hp = left.split(":")
        ap = right.split(":", 1)
        if len(hp) == 2 and len(ap) == 2:
            return _build_proxy(scheme, hp[0], hp[1], source, ap[0], ap[1])
    parts = body.split(":")
    if len(parts) == 2:
        return _build_proxy(scheme, parts[0], parts[1], source)
    if len(parts) >= 4 and _is_valid_host_port(parts[0], parts[1]):
        return _build_proxy(scheme, parts[0], parts[1], source, parts[2], ":".join(parts[3:]))
    if len(parts) >= 4 and _is_valid_host_port(parts[-2], parts[-1]):
        return _build_proxy(scheme, parts[-2], parts[-1], source, parts[0], ":".join(parts[1:-2]))
    return None


def _read_proxy_file_details() -> tuple[list[ProxyEntry], list[str]]:
    if not os.path.exists(PROXY_FILE):
        return [], []
    proxies: list[ProxyEntry] = []
    invalid: list[str]        = []
    seen:    set[str]         = set()
    with open(PROXY_FILE, "r", encoding="utf-8") as fh:
        for raw in fh:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for val in [p.strip() for p in stripped.split(",") if p.strip()]:
                e = _parse_proxy_value(val)
                if e and e.source not in seen:
                    proxies.append(e)
                    seen.add(e.source)
                elif not e:
                    invalid.append(val)
    return proxies, invalid


# ── فحص الـ pool الموجود ──────────────────────────────────────────────────────

def check_proxy_alive(proxy: ProxyEntry, timeout: int = PROXY_TEST_TIMEOUT) -> ProxyCheckResult:
    started = time.perf_counter()
    for url in _FF_TEST_URLS:
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "TSun-Proxy-Checker/1.0"},
                proxies=proxy.as_requests_proxies(),
                timeout=timeout,
                verify=False,
                allow_redirects=True,
            )
            elapsed = time.perf_counter() - started
            if resp.status_code != 407:
                return ProxyCheckResult(proxy, True, f"HTTP {resp.status_code}", elapsed)
        except requests.exceptions.RequestException:
            continue
    elapsed = time.perf_counter() - started
    return ProxyCheckResult(proxy, False, "failed on FF servers", elapsed)


def check_proxy_pool(
    timeout: int = PROXY_TEST_TIMEOUT,
    max_workers: int | None = None,
    on_result: Callable[[ProxyCheckResult, int, int], None] | None = None,
) -> ProxyCheckSummary:
    """يفحص كل proxies.txt على سيرفر FF ويحذف الميتة."""
    proxies, invalid_lines = _read_proxy_file_details()
    if not proxies:
        return ProxyCheckSummary([], [], invalid_lines, PROXY_FILE, OFFLINE_PROXY_FILE)

    workers = max_workers or min(50, len(proxies))
    alive: list[ProxyCheckResult] = []
    dead:  list[ProxyCheckResult] = []
    done   = 0

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(check_proxy_alive, p, timeout) for p in proxies]
        for f in as_completed(futs):
            r    = f.result()
            done += 1
            (alive if r.is_alive else dead).append(r)
            if on_result:
                on_result(r, done, len(proxies))

    save_proxy_check_results(alive, dead, invalid_lines)
    return ProxyCheckSummary(alive, dead, invalid_lines, PROXY_FILE, OFFLINE_PROXY_FILE)


def save_proxy_check_results(
    alive: list[ProxyCheckResult],
    dead:  list[ProxyCheckResult],
    invalid_lines: list[str],
) -> tuple[str, str]:
    alive_sources = [r.proxy.source for r in alive]
    dead_sources  = [r.proxy.source for r in dead] + invalid_lines

    with open(PROXY_FILE, "w", encoding="utf-8", newline="\n") as fh:
        if alive_sources:
            fh.write("\n".join(alive_sources) + "\n")

    existing: list[str] = []
    if os.path.exists(OFFLINE_PROXY_FILE):
        with open(OFFLINE_PROXY_FILE, "r", encoding="utf-8") as fh:
            existing = [l.strip() for l in fh if l.strip() and not l.strip().startswith("#")]
    merged = list(dict.fromkeys(existing + dead_sources))
    with open(OFFLINE_PROXY_FILE, "w", encoding="utf-8", newline="\n") as fh:
        if merged:
            fh.write("\n".join(merged) + "\n")

    refresh_proxy_pool()
    return PROXY_FILE, OFFLINE_PROXY_FILE


# ── تشغيل تلقائي عند الاستيراد ───────────────────────────────────────────────

def _auto_init() -> None:
    """يحمّل proxies.txt أولاً ثم يطلق internet refill في الخلفية."""
    global _ACTIVE_PROXY, _READY_QUEUE
    with _LOCK:
        entries, _ = _read_proxy_file_details()
        for e in entries:
            _READY_QUEUE.append(e)
        if _ACTIVE_PROXY is None and _READY_QUEUE:
            _ACTIVE_PROXY = _READY_QUEUE.pop(0)
    _trigger_refill()


_auto_init()
