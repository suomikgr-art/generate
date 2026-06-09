# Credits: TSun × Kittens
"""
storage/file_ops.py
~~~~~~~~~~~~~~~~~~~
Thread-safe JSON persistence for accounts, JWT tokens, rare accounts,
and couples accounts.  Every write goes through a per-file lock and uses
an atomic temp-file → rename pattern to prevent corruption.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime

import config.settings as settings
from ui.display import print_error

# ── Per-file locking ──────────────────────────────────────────────────────────

_FILE_LOCKS: dict[str, threading.Lock] = {}
_LOCK_REGISTRY = threading.Lock()


def _get_file_lock(filename: str) -> threading.Lock:
    with _LOCK_REGISTRY:
        if filename not in _FILE_LOCKS:
            _FILE_LOCKS[filename] = threading.Lock()
        return _FILE_LOCKS[filename]


# ── Atomic JSON write helper ──────────────────────────────────────────────────

def _atomic_json_write(filepath: str, data: list) -> None:
    """Write *data* to *filepath* atomically via a temporary file."""
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, filepath)


def _load_json_list(filepath: str) -> list:
    """Load a JSON list from *filepath*, returning [] on any error."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


# ── Save helpers ──────────────────────────────────────────────────────────────

def save_normal_account(account_data: dict, region: str, is_ghost: bool = False) -> bool:
    """
    Persist a newly generated account to the appropriate accounts JSON file.
    Returns True if the account was newly added, False if it already existed.
    """
    try:
        if is_ghost:
            filepath = os.path.join(settings.GHOST_ACCOUNTS_FOLDER, "ghost.json")
        else:
            filepath = os.path.join(settings.ACCOUNTS_FOLDER, f"accounts-{region}.json")

        entry = {
            "uid":          account_data["uid"],
            "password":     account_data["password"],
            "account_id":   account_data.get("account_id", "N/A"),
            "name":         account_data["name"],
            "region":       "TSun" if is_ghost else region,
            "date_created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "thread_id":    account_data.get("thread_id", "N/A"),
        }

        lock = _get_file_lock(filepath)
        with lock:
            records = _load_json_list(filepath)
            if account_data.get("account_id", "N/A") in {r.get("account_id") for r in records}:
                return False
            records.append(entry)
            _atomic_json_write(filepath, records)
        return True

    except Exception as e:
        print_error(f"Error saving account: {e}")
        return False


def save_jwt_token(
    account_data: dict,
    jwt_token: str,
    region: str,
    is_ghost: bool = False,
) -> bool:
    """
    Persist a JWT token record.
    Returns True if newly added, False if already present.
    """
    try:
        if is_ghost:
            filepath = os.path.join(settings.GHOST_FOLDER, "tokens-ghost.json")
        else:
            filepath = os.path.join(settings.TOKENS_FOLDER, f"tokens-{region}.json")

        entry = {
            "uid":        account_data["uid"],
            "account_id": account_data.get("account_id", "N/A"),
            "jwt_token":  jwt_token,
            "name":       account_data["name"],
            "password":   account_data["password"],
            "date_time":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "region":     "TSun" if is_ghost else region,
            "thread_id":  account_data.get("thread_id", "N/A"),
        }

        lock = _get_file_lock(filepath)
        with lock:
            records = _load_json_list(filepath)
            if account_data.get("account_id", "N/A") in {r.get("account_id") for r in records}:
                return False
            records.append(entry)
            _atomic_json_write(filepath, records)
        return True

    except Exception as e:
        print_error(f"Error saving JWT token: {e}")
        return False


def save_rare_account(
    account_data: dict,
    rarity_type: str,
    reason: str,
    rarity_score: int,
    is_ghost: bool = False,
) -> bool:
    """
    Persist a rare-account record.
    Returns True if newly added, False if already present.
    """
    try:
        if is_ghost:
            filepath = os.path.join(settings.GHOST_RARE_FOLDER, "rare-ghost.json")
        else:
            region = account_data.get("region", "UNKNOWN")
            filepath = os.path.join(settings.RARE_ACCOUNTS_FOLDER, f"rare-{region}.json")

        entry = {
            "uid":             account_data["uid"],
            "password":        account_data["password"],
            "account_id":      account_data.get("account_id", "N/A"),
            "name":            account_data["name"],
            "region":          "TSun" if is_ghost else account_data.get("region", "UNKNOWN"),
            "rarity_type":     rarity_type,
            "rarity_score":    rarity_score,
            "reason":          reason,
            "date_identified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "jwt_token":       account_data.get("jwt_token", ""),
            "thread_id":       account_data.get("thread_id", "N/A"),
        }

        lock = _get_file_lock(filepath)
        with lock:
            records = _load_json_list(filepath)
            if account_data.get("account_id", "N/A") in {r.get("account_id") for r in records}:
                return False
            records.append(entry)
            _atomic_json_write(filepath, records)
        return True

    except Exception as e:
        print_error(f"Error saving rare account: {e}")
        return False


def save_couples_account(
    account1: dict,
    account2: dict,
    reason: str,
    is_ghost: bool = False,
) -> bool:
    """
    Persist a couples-account pair record.
    Returns True if newly added, False if already present.
    """
    try:
        if is_ghost:
            filepath = os.path.join(settings.GHOST_COUPLES_FOLDER, "couples-ghost.json")
        else:
            region = account1.get("region", "UNKNOWN")
            filepath = os.path.join(settings.COUPLES_ACCOUNTS_FOLDER, f"couples-{region}.json")

        couple_id = f"{account1.get('account_id', 'N/A')}_{account2.get('account_id', 'N/A')}"
        entry = {
            "couple_id": couple_id,
            "account1": {
                "uid":        account1["uid"],
                "password":   account1["password"],
                "account_id": account1.get("account_id", "N/A"),
                "name":       account1["name"],
                "thread_id":  account1.get("thread_id", "N/A"),
            },
            "account2": {
                "uid":        account2["uid"],
                "password":   account2["password"],
                "account_id": account2.get("account_id", "N/A"),
                "name":       account2["name"],
                "thread_id":  account2.get("thread_id", "N/A"),
            },
            "reason":       reason,
            "region":       "TSun" if is_ghost else account1.get("region", "UNKNOWN"),
            "date_matched": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        lock = _get_file_lock(filepath)
        with lock:
            records = _load_json_list(filepath)
            if couple_id in {r.get("couple_id") for r in records}:
                return False
            records.append(entry)
            _atomic_json_write(filepath, records)
        return True

    except Exception as e:
        print_error(f"Error saving couples account: {e}")
        return False
