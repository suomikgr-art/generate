# Credits: TSun × Kittens
"""
features/couples.py
~~~~~~~~~~~~~~~~~~~
Couples-account detection: cross-thread matching of account pairs
that share special numeric relationships (sequential, mirror, etc.).
"""

from __future__ import annotations

import threading
from datetime import datetime

# ── Module-level state ────────────────────────────────────────────────────────

POTENTIAL_COUPLES: dict[str, dict] = {}
COUPLES_LOCK = threading.Lock()

# ── Pattern definitions (regex groups) ───────────────────────────────────────

ACCOUNT_COUPLES_PATTERNS: dict[str, list[str]] = {
    "MATCHING_PAIRS": [
        r"(\d{2})01.*\d{2}02",
        r"(\d{2})11.*\d{2}12",
        r"(\d{2})21.*\d{2}22",
    ],
    "COMPLEMENTARY_DIGITS": [
        r".*13.*14$",
        r".*07.*08$",
        r".*51.*52$",
    ],
    "LOVE_NUMBERS": [
        r".*520.*521$",
        r".*1314$",
    ],
}


# ── Pair analysis ─────────────────────────────────────────────────────────────

def _are_couple(id1: str, id2: str) -> tuple[bool, str | None]:
    """
    Check whether two account IDs form a 'couple' pair.

    Returns (matched, reason).
    """
    # Sequential
    try:
        if abs(int(id1) - int(id2)) == 1:
            return True, f"Sequential Account IDs: {id1} & {id2}"
    except ValueError:
        pass

    # Mirror
    if id1 and id2 and id1 == id2[::-1]:
        return True, f"Mirror Account IDs: {id1} & {id2}"

    # Complementary sum
    try:
        total = int(id1) + int(id2)
        if total % 1_000 == 0 or total % 10_000 == 0:
            return True, f"Complementary sum: {id1} + {id2} = {total}"
    except ValueError:
        pass

    # Love numbers
    for love_num in ("520", "521", "1314", "3344"):
        if love_num in id1 and love_num in id2:
            return True, f"Both contain love number: {love_num}"

    return False, None


# ── Public interface ──────────────────────────────────────────────────────────

def check_account_couples(
    account_data: dict,
    thread_id: int,
) -> tuple[bool, str | None, dict | None]:
    """
    Try to match *account_data* against previously seen accounts.

    If a match is found the partner is removed from the pool and returned.
    Otherwise the account is added to the pool for future matching.

    Returns (is_couple, reason, partner_data).
    """
    account_id: str = account_data.get("account_id", "")
    if account_id == "N/A" or not account_id:
        return False, None, None

    with COUPLES_LOCK:
        for stored_id, stored_data in list(POTENTIAL_COUPLES.items()):
            matched, reason = _are_couple(account_id, stored_data.get("account_id", ""))
            if matched:
                del POTENTIAL_COUPLES[stored_id]
                return True, reason, stored_data

        # No match found — park this account for future pairing
        POTENTIAL_COUPLES[account_id] = {
            "uid":        account_data.get("uid", ""),
            "account_id": account_id,
            "name":       account_data.get("name", ""),
            "password":   account_data.get("password", ""),
            "region":     account_data.get("region", ""),
            "thread_id":  thread_id,
            "timestamp":  datetime.now().isoformat(),
        }

    return False, None, None
