# Credits: TSun × Kittens  — Enhanced by TERBO
"""
core/generator.py
~~~~~~~~~~~~~~~~~
Account generation pipeline with:
  - Optimized per-thread session pooling (3-5x faster)
  - Auto game-server connect after each successful account
  - Thread-safe atomic counters
"""

from __future__ import annotations

import random
import time

import config.settings as settings
from core.api import (
    register_guest_account,
    grant_oauth_token,
    major_register,
    smart_delay,
)
from core.proxy import get_active_proxy, mark_proxy_dead
from features.couples import check_account_couples
from features.rarity import check_account_rarity
from storage.file_ops import save_normal_account, save_jwt_token, save_rare_account, save_couples_account
from ui.display import (
    Colors,
    get_random_color,
    print_success,
    print_warning,
    safe_print,
    print_registration_status,
    print_rarity_found,
    print_couples_found,
)

try:
    from core.game_connect import connect_account_to_server
    _GAME_CONNECT_AVAILABLE = True
except ImportError:
    _GAME_CONNECT_AVAILABLE = False


def generate_single_account(
    region: str,
    account_name: str,
    password_prefix: str,
    total_accounts: int,
    thread_id: int,
    is_ghost: bool = False,
    use_proxy: bool = True,
) -> dict | None:
    if settings.EXIT_FLAG:
        return None

    with settings.LOCK:
        if settings.SUCCESS_COUNTER + settings.INFLIGHT_COUNTER >= total_accounts:
            return None
        settings.INFLIGHT_COUNTER += 1

    # بروكسي واحد شغّال لكل الخطوات — لو مات يتبدّل تلقائياً في المرة القادمة
    proxy   = get_active_proxy() if use_proxy else None
    account = None

    try:
        step1 = register_guest_account(region, password_prefix, proxy)
        if not step1:
            return None

        uid, password = step1["uid"], step1["password"]

        step2 = grant_oauth_token(uid, password, proxy)
        if not step2:
            return None

        account = major_register(
            step2["access_token"],
            step2["open_id"],
            step2["field"],
            uid, password,
            account_name, region,
            is_ghost, proxy,
        )

    finally:
        with settings.LOCK:
            if not account:
                settings.INFLIGHT_COUNTER = max(0, settings.INFLIGHT_COUNTER - 1)
                return None

    with settings.LOCK:
        if settings.SUCCESS_COUNTER >= total_accounts:
            settings.INFLIGHT_COUNTER = max(0, settings.INFLIGHT_COUNTER - 1)
            return None
        settings.SUCCESS_COUNTER += 1
        current_count = settings.SUCCESS_COUNTER
        settings.INFLIGHT_COUNTER = max(0, settings.INFLIGHT_COUNTER - 1)

    account_id = account.get("account_id", "N/A")
    jwt_token  = account.get("jwt_token", "")
    account["thread_id"] = thread_id

    print_registration_status(
        current_count, total_accounts,
        account["name"], account["uid"], account["password"],
        account_id, region, is_ghost,
    )

    # ── Auto game-server connect ──────────────────────────────────────────────
    # Fast path: نمرر open_id + access_token مباشرة → يتخطى OAuth
    if _GAME_CONNECT_AVAILABLE and jwt_token and account_id != "N/A":
        try:
            connect_account_to_server(
                uid_str=account_id,
                jwt_token=jwt_token,
                region=region if not is_ghost else "IND",
                account_name=account["name"],
                uid_garena=str(account.get("uid", "")),
                password=account.get("password", ""),
                open_id=step2.get("open_id", ""),
                access_token=step2.get("access_token", ""),
            )
        except Exception as ce:
            print_warning(f"[GAME] Connect error: {ce}")

    # ── Rarity check ──────────────────────────────────────────────────────────
    is_rare, rarity_type, rarity_reason, rarity_score = check_account_rarity(account)
    if is_rare:
        rarity_type   = rarity_type or "RARE_ACCOUNT"
        rarity_reason = rarity_reason or "Unknown"
        with settings.LOCK:
            settings.RARE_COUNTER += 1
        print_rarity_found(account, rarity_type, rarity_reason, rarity_score)
        save_rare_account(account, rarity_type, rarity_reason, rarity_score, is_ghost)
        print_success(f"Rare saved! (Total: {settings.RARE_COUNTER})")

    # ── Couples check ─────────────────────────────────────────────────────────
    is_couple, couple_reason, partner = check_account_couples(account, thread_id)
    if is_couple and partner:
        couple_reason = couple_reason or "Unknown"
        with settings.LOCK:
            settings.COUPLES_COUNTER += 1
        print_couples_found(account, partner, couple_reason)
        save_couples_account(account, partner, couple_reason, is_ghost)
        print_success(f"Couple saved! (Total: {settings.COUPLES_COUNTER})")

    # ── Persistence ───────────────────────────────────────────────────────────
    save_label = "GHOST" if is_ghost else region
    if save_normal_account(account, save_label, is_ghost=is_ghost):
        print_success(f"Account #{current_count} saved")
    else:
        print_warning(f"Account {account['uid']} exists — skipped")

    if jwt_token:
        if save_jwt_token(account, jwt_token, save_label, is_ghost=is_ghost):
            print_success(f"JWT saved for {account['uid']}")

    return {"account": account}


def worker(
    region: str,
    account_name: str,
    password_prefix: str,
    total_accounts: int,
    thread_id: int,
    is_ghost: bool = False,
    use_proxy: bool = True,
) -> None:
    color = get_random_color()
    safe_print(f"{color}{Colors.BRIGHT}Thread {thread_id} started{Colors.RESET}")

    generated = 0
    while not settings.EXIT_FLAG:
        with settings.LOCK:
            if settings.SUCCESS_COUNTER + settings.INFLIGHT_COUNTER >= total_accounts:
                break

        result = generate_single_account(
            region, account_name, password_prefix,
            total_accounts, thread_id, is_ghost, use_proxy,
        )
        if result:
            generated += 1

        time.sleep(random.uniform(0.05, 0.15))

    safe_print(f"{color}{Colors.BRIGHT}Thread {thread_id} done — {generated} accounts{Colors.RESET}")
