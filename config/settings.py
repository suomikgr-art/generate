# Credits: TSun × Kittens
"""
config/settings.py
~~~~~~~~~~~~~~~~~~
Centralised configuration: region maps, storage paths, AES keys,
and shared mutable runtime state used across all modules.
"""

from __future__ import annotations

import os
import threading

# ── Shared Runtime State ──────────────────────────────────────────────────────
# All modules must access these via `import config.settings as settings`
# and mutate them as `settings.EXIT_FLAG = True`, etc.

EXIT_FLAG: bool = False
SUCCESS_COUNTER: int = 0
INFLIGHT_COUNTER: int = 0
TARGET_ACCOUNTS: int = 0
RARE_COUNTER: int = 0
COUPLES_COUNTER: int = 0
RARITY_SCORE_THRESHOLD: int = 3

LOCK = threading.Lock()

# ── Credentials / Keys ────────────────────────────────────────────────────────

_HEX_KEY = "32656534343831396539623435393838343531343130363762323831363231383734643064356437616639643866376530306331653534373135623764316533"
KEY = bytes.fromhex(_HEX_KEY)

CLIENT_DATA = "\U0001f480 PREMIUM ACCOUNT GENERATOR \U0001f525 By TSun × Kittens \U0001f525"
GARENA = "eFNhZWVk"

# ── Region Maps ───────────────────────────────────────────────────────────────

REGION_LANG: dict[str, str] = {
    "ME":  "ar",
    "IND": "hi",
    "ID":  "id",
    "VN":  "vi",
    "TH":  "th",
    "BD":  "bn",
    "PK":  "ur",
    "TW":  "zh",
    "CIS": "ru",
    "SG":  "en",
    "SAC": "es",
    "BR":  "pt",
}

REGION_URLS: dict[str, str] = {
    "IND": "https://client.ind.freefiremobile.com/",
    "ID":  "https://clientbp.ggblueshark.com/",
    "BR":  "https://client.us.freefiremobile.com/",
    "ME":  "https://clientbp.common.ggbluefox.com/",
    "VN":  "https://clientbp.ggblueshark.com/",
    "TH":  "https://clientbp.common.ggbluefox.com/",
    "CIS": "https://clientbp.ggblueshark.com/",
    "BD":  "https://clientbp.ggblueshark.com/",
    "PK":  "https://clientbp.ggblueshark.com/",
    "SG":  "https://clientbp.ggblueshark.com/",
    "SAC": "https://client.us.freefiremobile.com/",
    "TW":  "https://clientbp.ggblueshark.com/",
}

# ── Storage Paths ─────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))   # .../config/
PROJECT_ROOT = os.path.dirname(_HERE)                 # project root

BASE_FOLDER             = os.path.join(PROJECT_ROOT, "TSun-Studio")
TOKENS_FOLDER           = os.path.join(BASE_FOLDER, "TOKENS-JWT")
ACCOUNTS_FOLDER         = os.path.join(BASE_FOLDER, "ACCOUNTS")
RARE_ACCOUNTS_FOLDER    = os.path.join(BASE_FOLDER, "RARE ACCOUNTS")
COUPLES_ACCOUNTS_FOLDER = os.path.join(BASE_FOLDER, "COUPLES ACCOUNTS")
GHOST_FOLDER            = os.path.join(BASE_FOLDER, "GHOST")
GHOST_ACCOUNTS_FOLDER   = os.path.join(GHOST_FOLDER, "ACCOUNTS")
GHOST_RARE_FOLDER       = os.path.join(GHOST_FOLDER, "RAREACCOUNT")
GHOST_COUPLES_FOLDER    = os.path.join(GHOST_FOLDER, "COUPLESACCOUNT")

# Create all required directories on import
for _d in [
    BASE_FOLDER, TOKENS_FOLDER, ACCOUNTS_FOLDER, RARE_ACCOUNTS_FOLDER,
    COUPLES_ACCOUNTS_FOLDER, GHOST_FOLDER, GHOST_ACCOUNTS_FOLDER,
    GHOST_RARE_FOLDER, GHOST_COUPLES_FOLDER,
]:
    os.makedirs(_d, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_region(language_code: str) -> str | None:
    """Return the region code for a given language code, or None."""
    return REGION_LANG.get(language_code)


def get_region_url(region_code: str) -> str:
    """Return the base URL for a given region code."""
    return REGION_URLS.get(region_code, "https://clientbp.ggblueshark.com/")
