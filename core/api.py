# Credits: TSun × Kittens  — Enhanced by TERBO
"""
core/api.py
~~~~~~~~~~~
All network calls to Garena and FreeFire endpoints:
  - Guest account registration
  - OAuth token grant
  - MajorRegister (in-game account setup)
  - MajorLogin (JWT extraction)
  - Region binding

Speed improvements:
  - Per-thread requests.Session with keep-alive connection pooling
  - Reduced random delays (0.05-0.25s instead of 0.35-0.9s)
  - Faster retry logic with minimal sleep
  - Adaptive backoff only on rate-limit responses
"""

from __future__ import annotations

import base64
import codecs
import hashlib
import hmac
import json
import random
import string
import threading
import time
from typing import Optional

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import config.settings as settings
from core.crypto import aes_encrypt_hex, aes_encrypt_to_hex, build_proto_packet
from core.proxy import ProxyEntry, mark_proxy_dead
from ui.display import print_success, print_warning

_REGISTER_URL   = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
_TOKEN_URL      = "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant"
_DIRECT_TIMEOUT = 20
_PROXY_TIMEOUT  = (5, 15)

_thread_local = threading.local()


def _get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=1,
            pool_maxsize=4,
            max_retries=0,
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _thread_local.session = s
    return _thread_local.session


def _request_proxies(proxy: ProxyEntry | None) -> dict[str, str] | None:
    return proxy.as_requests_proxies() if proxy else None


def _request_timeout(proxy: ProxyEntry | None) -> int | tuple[int, int]:
    return _PROXY_TIMEOUT if proxy else _DIRECT_TIMEOUT


def _request_context(proxy: ProxyEntry | None) -> str:
    return f" via {proxy.label}" if proxy else ""


def _format_request_error(exc: Exception) -> str:
    if isinstance(exc, requests.exceptions.ProxyError):
        return "proxy auth failed (407)" if "407" in str(exc) else "proxy failed"
    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, requests.exceptions.SSLError):
        return "SSL failed"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "connection failed"
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return f"HTTP {exc.response.status_code}"
    return str(exc)


# ── Name / Password generation ────────────────────────────────────────────

# حروف كابيتال + أرقام + رموز مميزة
_UPPER   = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS  = "0123456789"
_SPECIAL = "@&#$!؟*+¹²³⁴⁵⁶⁷⁸⁹⁰∅|√π•÷×§∆£¢€¥^°©®™٪✓"
_MIXED   = _UPPER + _DIGITS + _SPECIAL

# ثابتة — لا تُعدّل من menus.py بعد الآن
NAME_SUFFIX_LEN: int  = 2       # السوفيكس دائماً 2 خانات
NAME_MAX_LEN: int     = 12      # الحد الأقصى للاسم الكلي
NAME_SUFFIX_TYPE: str = "mixed"

# تتبع الأسماء المستخدمة لضمان عدم التكرار
_USED_NAMES: set = set()


def _generate_suffix() -> str:
    """يولدّ سوفيكس 2 خانة من حروف كابيتال + أرقام + رموز."""
    return "".join(random.choice(_MIXED) for _ in range(NAME_SUFFIX_LEN))


def _is_arabic(text: str) -> bool:
    """يكتشف تلقائياً إذا النص يحتوي على حروف عربية."""
    for ch in text:
        cp = ord(ch)
        if (0x0600 <= cp <= 0x06FF or   # العربية الأساسية
            0x0750 <= cp <= 0x077F or   # عربية إضافية
            0x08A0 <= cp <= 0x08FF or   # عربية موسعة
            0xFB50 <= cp <= 0xFDFF or   # أشكال عربية مقدمة
            0xFE70 <= cp <= 0xFEFF):    # أشكال عربية مقدمة-ب
            return True
    return False


def generate_random_name(base_name: str) -> str:
    """
    يبني اسماً فريداً — يكتشف لغة الاسم تلقائياً:
      عربي:   prefix + suffix + ㅤ   مثال: محمدM2ㅤ
      إنجليزي: prefix + ㅤ + suffix  مثال: ALIㅤM2
    السوفيكس دائماً 2 خانات من _MIXED.
    """
    max_prefix = max(1, NAME_MAX_LEN - 1 - NAME_SUFFIX_LEN)
    prefix     = base_name[:max_prefix]
    arabic     = _is_arabic(prefix)
    for _ in range(10_000):
        suffix = _generate_suffix()
        if arabic:
            name = prefix + suffix + "ㅤ"
        else:
            name = prefix + "ㅤ" + suffix
        if name not in _USED_NAMES:
            _USED_NAMES.add(name)
            return name
    # احتياطي: أضف رقم عشوائي
    suffix = _generate_suffix() + str(random.randint(0, 9))
    if arabic:
        return prefix + suffix + "ㅤ"
    return prefix + "ㅤ" + suffix

def generate_custom_password(prefix: str) -> str:
    garena = base64.b64decode(settings.GARENA).decode("utf-8")
    chars  = string.ascii_uppercase + string.digits
    part1  = "".join(random.choice(chars) for _ in range(5))
    part2  = "".join(random.choice(chars) for _ in range(5))
    return f"{prefix}_{part1}_{garena}_{part2}"


# ── Delay (optimized — much shorter) ─────────────────────────────────────────

def smart_delay(low: float = 0.05, high: float = 0.2) -> None:
    time.sleep(random.uniform(low, high))


def _rate_limit_backoff(attempt: int) -> None:
    wait = min(0.5 * (2 ** attempt), 8.0) + random.uniform(0, 0.5)
    time.sleep(wait)


# ── Token encoding helpers ────────────────────────────────────────────────────

def _encode_open_id(original: str) -> dict[str, str]:
    keystream = [
        0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37, 0x30,
        0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37,
        0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31,
        0x37, 0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30,
    ]
    encoded = "".join(
        chr(ord(c) ^ keystream[i % len(keystream)]) for i, c in enumerate(original)
    )
    return {"open_id": original, "field_14": encoded}


def _to_unicode_escaped(s: str) -> str:
    return "".join(c if 32 <= ord(c) <= 126 else f"\\u{ord(c):04x}" for c in s)


# ── JWT decoding ──────────────────────────────────────────────────────────────

def decode_jwt_token(jwt_token: str) -> str:
    try:
        parts = jwt_token.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            data       = json.loads(base64.urlsafe_b64decode(payload))
            account_id = data.get("account_id") or data.get("external_id")
            if account_id:
                return str(account_id)
    except Exception as e:
        print_warning(f"JWT decode failed: {e}")
    return "N/A"


# ── API calls ─────────────────────────────────────────────────────────────────

def register_guest_account(
    region: str,
    password_prefix: str,
    proxy: ProxyEntry | None = None,
) -> Optional[dict]:
    if settings.EXIT_FLAG:
        return None
    try:
        session  = _get_session()
        password = generate_custom_password(password_prefix)
        payload  = {"app_id": 100067, "client_type": 2, "password": password, "source": 2}
        body_json = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(settings.KEY, body_json.encode("utf-8"), hashlib.sha256).hexdigest()

        headers = {
            "User-Agent":   "GarenaMSDK/4.0.39(SM-A325M ;Android 13;en;HK;)",
            "Authorization": f"Signature {signature}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept":       "application/json",
            "Connection":   "Keep-Alive",
            "Host":         "100067.connect.garena.com",
        }

        proxies = _request_proxies(proxy)
        timeout = _request_timeout(proxy)

        for attempt in range(3):
            response = session.post(
                _REGISTER_URL, headers=headers, data=body_json,
                proxies=proxies, timeout=timeout, verify=False,
            )
            if response.status_code not in (403, 429):
                break
            _rate_limit_backoff(attempt)

        if response.status_code in (403, 429):
            print_warning(f"Register blocked ({response.status_code}){_request_context(proxy)}")
            if response.status_code == 429:
                mark_proxy_dead(proxy)   # محروق — أزله من الـ pool
            smart_delay()
            return None

        response.raise_for_status()
        body = response.json()
        data = body.get("data", body)

        if (body.get("code", 0) == 0 and "uid" in data) or "uid" in body:
            uid = data.get("uid") or body.get("uid")
            print_success(f"Registered: {uid}")
            smart_delay()
            return {"uid": uid, "password": password}
        return None

    except Exception as e:
        mark_proxy_dead(proxy)   # فشل كامل — أزله من الـ pool
        print_warning(f"Register failed{_request_context(proxy)}: {_format_request_error(e)}")
        smart_delay()
        return None


def grant_oauth_token(
    uid: str,
    password: str,
    proxy: ProxyEntry | None = None,
) -> Optional[dict]:
    if settings.EXIT_FLAG:
        return None
    try:
        session       = _get_session()
        client_secret = settings.KEY.decode("ascii")
        payload = {
            "client_id": 100067, "client_secret": client_secret,
            "client_type": 2, "password": password,
            "response_type": "token", "uid": uid,
        }
        body_json = json.dumps(payload, separators=(",", ":"))
        signature = hmac.new(settings.KEY, body_json.encode("utf-8"), hashlib.sha256).hexdigest()

        headers = {
            "User-Agent":   "GarenaMSDK/4.0.39(SM-A325M ;Android 13;en;HK;)",
            "Authorization": f"Signature {signature}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept":       "application/json",
            "Connection":   "Keep-Alive",
            "Host":         "100067.connect.garena.com",
        }

        proxies = _request_proxies(proxy)
        timeout = _request_timeout(proxy)

        for attempt in range(3):
            response = session.post(
                _TOKEN_URL, headers=headers, data=body_json,
                proxies=proxies, timeout=timeout, verify=False,
            )
            if response.status_code not in (403, 429):
                break
            _rate_limit_backoff(attempt)

        if response.status_code in (403, 429):
            print_warning(f"Token blocked ({response.status_code}){_request_context(proxy)}")
            if response.status_code == 429:
                mark_proxy_dead(proxy)   # محروق — أزله من الـ pool
            smart_delay()
            return None

        response.raise_for_status()
        body = response.json()
        data = body.get("data", body)

        if body.get("code", 0) == 0 and "open_id" in data:
            open_id      = data["open_id"]
            access_token = data["access_token"]
            result       = _encode_open_id(open_id)
            field_raw    = _to_unicode_escaped(result["field_14"])
            field        = codecs.decode(field_raw, "unicode_escape").encode("latin1")
            print_success(f"Token granted: {uid}")
            smart_delay()
            return {
                "open_id":      open_id,
                "access_token": access_token,
                "refresh_token": data.get("refresh_token", ""),
                "field":        field,
            }
        return None

    except Exception as e:
        mark_proxy_dead(proxy)   # فشل كامل — أزله من الـ pool
        print_warning(f"Token grant failed{_request_context(proxy)}: {_format_request_error(e)}")
        smart_delay()
        return None


def major_register(
    access_token: str,
    open_id: str,
    field: bytes,
    uid: str,
    password: str,
    account_name: str,
    region: str,
    is_ghost: bool = False,
    proxy: ProxyEntry | None = None,
) -> Optional[dict]:
    if settings.EXIT_FLAG:
        return None
    try:
        session = _get_session()

        name      = generate_random_name(account_name)
        lang_code = "pt" if is_ghost else settings.REGION_LANG.get(region.upper(), "en")

        payload_fields = {
            1: name, 2: access_token, 3: open_id,
            5: 102000007, 6: 4, 7: 1, 13: 1,
            14: field, 15: lang_code, 16: 1, 17: 1,
        }
        proto_bytes       = build_proto_packet(payload_fields)
        encrypted_payload = aes_encrypt_hex(proto_bytes.hex())

        proxies = _request_proxies(proxy)

        # blueshark يقبل كل الـ regions بما فيها ME/TH
        endpoints = [("https://loginbp.ggblueshark.com/MajorRegister", "loginbp.ggblueshark.com")]

        response = None
        for ep_url, ep_host in endpoints:
            try:
                response = session.post(
                    ep_url,
                    headers={
                        "Accept-Encoding": "gzip",
                        "Authorization":   "Bearer",
                        "Connection":      "Keep-Alive",
                        "Content-Type":    "application/x-www-form-urlencoded",
                        "Expect":          "100-continue",
                        "Host":            ep_host,
                        "ReleaseVersion":  "OB53",
                        "User-Agent":      "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
                        "X-GA":            "v1 1",
                        "X-Unity-Version": "2018.4.11f1",
                    },
                    data=encrypted_payload,
                    proxies=proxies,
                    verify=False,
                    timeout=_request_timeout(proxy),
                )
                if response.status_code == 200:
                    break
            except Exception:
                continue

        if response is None or response.status_code != 200:
            code = response.status_code if response is not None else "N/A"
            body = ""
            try:
                body = response.content[:300].hex()
            except Exception:
                pass
            print_warning(f"MajorRegister {code} | body_hex: {body}{_request_context(proxy)}")
            return None

        print_success(f"MajorRegister OK: {name}")

        login_result = major_login(uid, password, access_token, open_id, region, is_ghost, proxy)
        account_id   = login_result.get("account_id", "N/A")
        jwt_token    = login_result.get("jwt_token", "")

        if not is_ghost and jwt_token and account_id != "N/A" and region.upper() != "BR":
            if bind_region(region, jwt_token, proxy):
                print_success(f"Region {region} bound")
            else:
                print_warning(f"Region bind failed for {region}")

        return {
            "uid":        uid,
            "password":   password,
            "name":       name,
            "region":     "GHOST" if is_ghost else region,
            "status":     "success",
            "account_id": account_id,
            "jwt_token":  jwt_token,
            "proxy":      proxy.label if proxy else "DIRECT",
        }

    except Exception as e:
        print_warning(f"MajorRegister failed{_request_context(proxy)}: {_format_request_error(e)}")
        smart_delay()
        return None


_LOGIN_PAYLOAD_PARTS = [
    b'\x1a\x132025-08-30 05:19:21"\tfree fire(\x01:\x081.114.13B2Android OS 9 / API-28'
    b' (PI/rel.cjw.20220518.114133)J\x08HandheldR\nATM MobilsZ\x04WIFI`\xb6\nh\xee\x05'
    b'r\x03300z\x1fARMv7 VFPv3 NEON VMH | 2400 | 2\x80\x01\xc9\x0f\x8a\x01\x0fAdreno (TM) 640'
    b'\x92\x01\rOpenGL ES 3.2\x9a\x01+Google|dfa4ab4b-9dc4-454e-8065-e70c733fa53f'
    b'\xa2\x01\x0e105.235.139.91\xaa\x01\x02',
    None,
    b'\xb2\x01 1d8ec0240ede109973f3321b9354b44d\xba\x01\x014\xc2\x01\x08Handheld'
    b'\xca\x01\x10Asus ASUS_I005DA\xea\x01@afcfbf13334be42036e4f742c80b956344bed760'
    b'ac91b3aff9b607a610ab4390\xf0\x01\x01\xca\x02\nATM Mobils\xd2\x02\x04WIFI'
    b'\xca\x03 7428b253defc164018c604a1ebbfebdf\xe0\x03\xa8\x81\x02\xe8\x03\xf6\xe5\x01'
    b'\xf0\x03\xaf\x13\xf8\x03\x84\x07\x80\x04\xe7\xf0\x01\x88\x04\xa8\x81\x02'
    b'\x90\x04\xe7\xf0\x01\x98\x04\xa8\x81\x02\xc8\x04\x01\xd2\x04=/data/app/'
    b'com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/lib/arm\xe0\x04\x01\xea\x04_'
    b'2087f61c19f57f2af4e7feff0b24d9d9|/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg=='
    b'/base.apk\xf0\x04\x03\xf8\x04\x01\x8a\x05\x0232\x9a\x05\n2019118692\xb2\x05'
    b'\tOpenGLES2\xb8\x05\xff\x7f\xc0\x05\x04\xe0\x05\xf3F\xea\x05\x07android'
    b'\xf2\x05pKqsHT5ZLWrYljNb5Vqh//yFRlaPHSO9NWSQsVvOmdhEEn7W+VHNUK+Q+fduA3pt'
    b'NrGB0Ll0LRz3WW0jOwesLj6aiU7sZ40p8BfUE/FI/jzSTwRe2\xf8\x05\xfb\xe4\x06'
    b'\x88\x06\x01\x90\x06\x01\x9a\x06\x014\xa2\x06\x014\xb2\x06"GQ@O\x00\x0e^'
    b'\x00D\x06UA\x0ePM\r\x13hZ\x07T\x06\x0cm\\V\x0ejYV;\x0bU5',
]

_ACCESS_TOKEN_PLACEHOLDER = b'afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390'
_OPEN_ID_PLACEHOLDER      = b'1d8ec0240ede109973f3321b9354b44d'


def major_login(
    uid: str,
    password: str,
    access_token: str,
    open_id: str,
    region: str,
    is_ghost: bool = False,
    proxy: ProxyEntry | None = None,
) -> dict:
    try:
        session = _get_session()
        lang    = "pt" if is_ghost else settings.REGION_LANG.get(region.upper(), "en")

        parts = list(_LOGIN_PAYLOAD_PARTS)
        parts[1] = lang.encode("ascii")
        raw_payload = b"".join(parts)
        raw_payload = raw_payload.replace(_ACCESS_TOKEN_PLACEHOLDER, access_token.encode())
        raw_payload = raw_payload.replace(_OPEN_ID_PLACEHOLDER, open_id.encode())

        encrypted_hex = aes_encrypt_to_hex(raw_payload.hex())
        final_payload = bytes.fromhex(encrypted_hex)

        # قائمة endpoints — نجرب الكل حتى يرجع JWT
        if is_ghost:
            endpoints = [
                ("https://loginbp.ggblueshark.com/MajorLogin",        "loginbp.ggblueshark.com"),
            ]
        elif region.upper() in ("ME", "TH"):
            endpoints = [
                ("https://loginbp.common.ggbluefox.com/MajorLogin",   "loginbp.common.ggbluefox.com"),
                ("https://loginbp.ggblueshark.com/MajorLogin",         "loginbp.ggblueshark.com"),
                ("https://loginbp.ggpolarbear.com/MajorLogin",         "loginbp.ggpolarbear.com"),
            ]
        else:
            endpoints = [
                ("https://loginbp.ggblueshark.com/MajorLogin",        "loginbp.ggblueshark.com"),
                ("https://loginbp.ggpolarbear.com/MajorLogin",        "loginbp.ggpolarbear.com"),
                ("https://loginbp.common.ggbluefox.com/MajorLogin",   "loginbp.common.ggbluefox.com"),
            ]

        proxies = _request_proxies(proxy)
        _valid  = frozenset(
            b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            b'abcdefghijklmnopqrstuvwxyz'
            b'0123456789-_.'
        )

        for attempt in range(2):          # حاول مرتين على كل endpoint
            for url, host in endpoints:
                try:
                    response = session.post(
                        url,
                        headers={
                            "Accept-Encoding": "gzip",
                            "Authorization":   "Bearer",
                            "Connection":      "Keep-Alive",
                            "Content-Type":    "application/x-www-form-urlencoded",
                            "Expect":          "100-continue",
                            "Host":            host,
                            "ReleaseVersion":  "OB53",
                            "User-Agent":      "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
                            "X-GA":            "v1 1",
                            "X-Unity-Version": "2018.4.11f1",
                        },
                        data=final_payload,
                        proxies=proxies,
                        verify=False,
                        timeout=_request_timeout(proxy),
                    )
                    if response.status_code != 200:
                        continue
                    content = response.content
                    idx = content.find(b"eyJ")
                    if idx == -1:
                        continue
                    end = idx
                    while end < len(content) and content[end] in _valid:
                        end += 1
                    jwt_raw = content[idx:end].decode("ascii", errors="ignore")
                    jwt_parts = jwt_raw.split(".")
                    if len(jwt_parts) >= 3:
                        jwt_token  = ".".join(jwt_parts[:3])
                        account_id = decode_jwt_token(jwt_token)
                        return {"account_id": account_id, "jwt_token": jwt_token}
                except Exception:
                    continue
            if attempt == 0:
                time.sleep(0.3)   # انتظر قليلاً قبل المحاولة الثانية

        return {"account_id": "N/A", "jwt_token": ""}

    except Exception as e:
        print_warning(f"MajorLogin failed{_request_context(proxy)}: {_format_request_error(e)}")
        return {"account_id": "N/A", "jwt_token": ""}


def bind_region(
    region: str,
    jwt_token: str,
    proxy: ProxyEntry | None = None,
) -> bool:
    try:
        session    = _get_session()
        url        = ("https://loginbp.common.ggbluefox.com/ChooseRegion"
                      if region.upper() in ("ME", "TH")
                      else "https://loginbp.ggblueshark.com/ChooseRegion")
        region_code = "RU" if region.upper() == "CIS" else region.upper()
        proto_data  = build_proto_packet({1: region_code})
        payload     = bytes.fromhex(aes_encrypt_to_hex(proto_data.hex()))

        proxies  = _request_proxies(proxy)
        response = session.post(
            url,
            data=payload,
            headers={
                "User-Agent":      "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
                "Connection":      "Keep-Alive",
                "Accept-Encoding": "gzip",
                "Content-Type":    "application/x-www-form-urlencoded",
                "Expect":          "100-continue",
                "Authorization":   f"Bearer {jwt_token}",
                "X-Unity-Version": "2018.4.11f1",
                "X-GA":            "v1 1",
                "ReleaseVersion":  "OB53",
            },
            proxies=proxies,
            verify=False,
            timeout=_request_timeout(proxy),
        )
        if response.status_code != 200:
            print_warning(f"ChooseRegion {response.status_code}: {response.text[:120]}")
        return response.status_code == 200

    except Exception as e:
        print_warning(f"ChooseRegion failed{_request_context(proxy)}: {_format_request_error(e)}")
        return False
