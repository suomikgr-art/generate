# Credits: TSun × Kittens
"""
features/rarity.py
~~~~~~~~~~~~~~~~~~
Rare-account detection: pattern definitions and scoring logic.
Accounts that reach or exceed RARITY_SCORE_THRESHOLD are considered rare.
"""

from __future__ import annotations

import re

import config.settings as settings

# ── Pattern registry ──────────────────────────────────────────────────────────
# Each entry: pattern_name -> [regex, score]

ACCOUNT_RARITY_PATTERNS: dict[str, list] = {
    "REPEATED_DIGITS_4":        [r"(\d)\1{3,}",                                                    3],
    "REPEATED_DIGITS_3":        [r"(\d)\1\1(\d)\2\2",                                              2],
    "SEQUENTIAL_5":             [r"(12345|23456|34567|45678|56789)",                                4],
    "SEQUENTIAL_4":             [r"(0123|1234|2345|3456|4567|5678|6789|9876|8765|7654|6543|5432|4321|3210)", 3],
    "PALINDROME_6":             [r"^(\d)(\d)(\d)\3\2\1$",                                          5],
    "PALINDROME_4":             [r"^(\d)(\d)\2\1$",                                                3],
    "SPECIAL_COMBINATIONS_HIGH":[r"(69|420|1337|007)",                                             4],
    "SPECIAL_COMBINATIONS_MED": [r"(100|200|300|400|500|666|777|888|999)",                         2],
    "QUADRUPLE_DIGITS":         [r"(1111|2222|3333|4444|5555|6666|7777|8888|9999|0000)",           4],
    "MIRROR_PATTERN_HIGH":      [r"^(\d{2,3})\1$",                                                 3],
    "MIRROR_PATTERN_MED":       [r"(\d{2})0\1",                                                    2],
    "GOLDEN_RATIO":             [r"1618|0618",                                                      3],
}


# ── Core check ───────────────────────────────────────────────────────────────

def check_account_rarity(
    account_data: dict,
) -> tuple[bool, str | None, str | None, int]:
    """
    Analyse an account's ID and return a rarity verdict.

    Returns
    -------
    (is_rare, rarity_type, reason, rarity_score)
    """
    account_id: str = account_data.get("account_id", "")
    if account_id == "N/A" or not account_id:
        return False, None, None, 0

    rarity_score = 0
    detected_patterns: list[str] = []

    # Regex-based patterns
    for pattern_name, (pattern, score) in ACCOUNT_RARITY_PATTERNS.items():
        if re.search(pattern, account_id):
            rarity_score += score
            detected_patterns.append(pattern_name)

    # Digit-level analysis
    digits = [int(d) for d in account_id if d.isdigit()]

    if len(set(digits)) == 1 and len(digits) >= 4:
        rarity_score += 5
        detected_patterns.append("UNIFORM_DIGITS")

    if len(digits) >= 4:
        diffs = [digits[i + 1] - digits[i] for i in range(len(digits) - 1)]
        if len(set(diffs)) == 1:
            rarity_score += 4
            detected_patterns.append("ARITHMETIC_SEQUENCE")

    if len(account_id) <= 8 and account_id.isdigit() and int(account_id) < 1_000_000:
        rarity_score += 3
        detected_patterns.append("LOW_ACCOUNT_ID")

    if rarity_score >= settings.RARITY_SCORE_THRESHOLD:
        reason = (
            f"Account ID {account_id} — "
            f"Score: {rarity_score} — "
            f"Patterns: {', '.join(detected_patterns)}"
        )
        return True, "RARE_ACCOUNT", reason, rarity_score

    return False, None, None, rarity_score
