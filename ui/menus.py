# Credits: TSun × Kittens
"""
ui/menus.py
~~~~~~~~~~~
Interactive CLI menus: main menu, account-generation flow,
saved-account viewer, and about screen.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

import psutil
from colorama import Fore

import config.settings as settings
from core.generator import worker
from core.proxy import PROXY_TEST_TIMEOUT, check_proxy_pool, refresh_proxy_pool
from ui.display import (
    Colors,
    clear_screen,
    display_banner,
    format_project_path,
    get_random_color,
    print_error,
    print_success,
    print_warning,
    safe_print,
    safe_exit,
)


# ── Utility ───────────────────────────────────────────────────────────────────

def wait_for_enter() -> None:
    print(f"\n{get_random_color()}{Colors.BRIGHT}⏎  Press Enter to continue...{Colors.RESET}")
    input()


# ── Generate Accounts flow ────────────────────────────────────────────────────

def generate_accounts_flow() -> None:
    global SUCCESS_COUNTER  # noqa: F841 (accessed via settings)

    clear_screen()
    display_banner()

    cpu_count          = psutil.cpu_count() or 1
    recommended_threads = min(cpu_count, 3)

    # ── Region selection ──────────────────────────────────────────────────────
    regions_to_show = sorted(r for r in settings.REGION_LANG if r != "BR")

    print(f"{get_random_color()}{Colors.BRIGHT}🌍 Available Regions:{Colors.RESET}")
    for i, region in enumerate(regions_to_show, 1):
        print(f"{get_random_color()}  {i}) {region} ({settings.REGION_LANG[region]}){Colors.RESET}")
    print(f"{get_random_color()}  {len(regions_to_show) + 1}) {Fore.LIGHTMAGENTA_EX}GHOST Mode{Colors.RESET}")
    print(f"{get_random_color()}  00)  {Fore.YELLOW}Back to Main Menu{Colors.RESET}")
    print(f"{get_random_color()}  000) {Fore.RED}Exit{Colors.RESET}")

    selected_region = ""
    is_ghost        = False

    while True:
        try:
            choice = input(f"\n{get_random_color()}{Colors.BRIGHT}🎯 Choose option: {Colors.RESET}").strip().upper()

            if choice == "00":
                return
            elif choice == "000":
                print(f"\n{get_random_color()}{Colors.BRIGHT}👋 Thank you for using TSun Generator!{Colors.RESET}")
                sys.exit(0)
            elif choice.isdigit():
                n = int(choice)
                if 1 <= n <= len(regions_to_show):
                    selected_region = regions_to_show[n - 1]
                    is_ghost = False
                    break
                elif n == len(regions_to_show) + 1:
                    selected_region = "BR"
                    is_ghost = True
                    break
                else:
                    print_error("Invalid option.")
            elif choice in regions_to_show:
                selected_region = choice
                is_ghost = False
                break
            elif choice == "GHOST":
                selected_region = "BR"
                is_ghost = True
                break
            else:
                print_error("Invalid option. Please choose a valid region or number.")
        except ValueError:
            print_error("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            safe_exit()

    clear_screen()
    display_banner()

    if is_ghost:
        print(f"{Fore.LIGHTMAGENTA_EX}{Colors.BRIGHT}🌍 Selected Mode: GHOST MODE{Colors.RESET}")
    else:
        print(f"{get_random_color()}{Colors.BRIGHT}🌍 Selected Region: {selected_region} ({settings.REGION_LANG[selected_region]}){Colors.RESET}")

    # ── Prompts ───────────────────────────────────────────────────────────────

    account_count = _prompt_int("🎯 How many accounts to generate", min_val=1)
    account_name  = _prompt_str("👤 Enter account name prefix (max 9 chars, rest is suffix)")

    import core.api as _api
    _api.NAME_MAX_LEN    = 12
    _api.NAME_SUFFIX_LEN = 2
    _api.NAME_SUFFIX_TYPE = "mixed"

    password_prefix = _prompt_str("🔑 Enter password prefix")

    while True:
        try:
            rarity_threshold = int(input(
                f"\n{get_random_color()}{Colors.BRIGHT}"
                f"⭐ Rarity score threshold (1–10, default 3): {Colors.RESET}"
            ))
            if 1 <= rarity_threshold <= 10:
                settings.RARITY_SCORE_THRESHOLD = rarity_threshold
                break
            print_error("Please enter a number between 1 and 10.")
        except ValueError:
            print_error("Invalid input.")
        except KeyboardInterrupt:
            safe_exit()

    thread_count = _prompt_int(f"🧵 Thread count (recommended: {recommended_threads})", min_val=1)
    use_proxy = _prompt_yes_no("Use proxies from proxies.txt? (y/n)")
    proxy_count = 0
    invalid_proxy_count = 0
    proxy_display_path = ""
    proxy_fallback_warning = False

    if use_proxy:
        proxy_count, invalid_proxy_count, proxy_file = refresh_proxy_pool()
        proxy_display_path = format_project_path(proxy_file)
        if proxy_count == 0:
            proxy_fallback_warning = True
            use_proxy = False

    # ── Summary & countdown ───────────────────────────────────────────────────
    clear_screen()
    display_banner()

    mode_label = "GHOST MODE" if is_ghost else selected_region
    print(f"{get_random_color()}{Colors.BRIGHT}🚀 Starting Account Generation — {mode_label}{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}🎯 Target:     {account_count}{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}👤 Name:       {account_name}{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}🔑 Password:   {password_prefix}{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}⭐ Rarity:     {settings.RARITY_SCORE_THRESHOLD}+{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}🧵 Threads:    {thread_count}{Colors.RESET}")
    if use_proxy:
        print(f"{get_random_color()}{Colors.BRIGHT}🌐 Proxies:    {proxy_count} rotating ({proxy_display_path}){Colors.RESET}")
    else:
        print(f"{get_random_color()}{Colors.BRIGHT}🌐 Network:    Original network (DIRECT){Colors.RESET}")
    if proxy_fallback_warning:
        print_warning("Proxy mode selected, but no valid proxies found. Using original network.")
    if invalid_proxy_count:
        print_warning(f"{invalid_proxy_count} invalid proxy line(s) ignored.")
    print(f"{get_random_color()}{Colors.BRIGHT}📁 Output:     {format_project_path(settings.ACCOUNTS_FOLDER)}{Colors.RESET}")
    print(f"\n{get_random_color()}{Colors.BRIGHT}⏳ Starting in 3 seconds...{Colors.RESET}")
    time.sleep(3)

    # ── Reset counters ────────────────────────────────────────────────────────
    settings.SUCCESS_COUNTER  = 0
    settings.TARGET_ACCOUNTS  = account_count
    settings.RARE_COUNTER     = 0
    settings.COUPLES_COUNTER  = 0
    settings.EXIT_FLAG        = False

    settings.INFLIGHT_COUNTER = 0
    start_time = time.time()
    threads: list[threading.Thread] = []

    print(f"\n{get_random_color()}{Colors.BRIGHT}🚀 Launching {thread_count} thread(s)...\n{Colors.RESET}")

    for i in range(thread_count):
        t = threading.Thread(
            target=worker,
            args=(
                selected_region,
                account_name,
                password_prefix,
                account_count,
                i + 1,
                is_ghost,
                use_proxy,
            ),
            daemon=True,
        )
        t.start()
        threads.append(t)

    # ── Progress monitor ──────────────────────────────────────────────────────
    try:
        last_status: tuple[int, int, int] | None = None
        last_status_time = 0.0
        while any(t.is_alive() for t in threads):
            time.sleep(2)
            with settings.LOCK:
                current = settings.SUCCESS_COUNTER
                rare_count = settings.RARE_COUNTER
                couples_count = settings.COUPLES_COUNTER
            pct = (current / account_count) * 100
            status = (current, rare_count, couples_count)
            now = time.time()
            if status != last_status or now - last_status_time >= 10:
                safe_print(
                    f"{get_random_color()}{Colors.BRIGHT}"
                    f"📊 Progress: {current}/{account_count} ({pct:.1f}%) | "
                    f"💎 Rare: {rare_count} | "
                    f"💑 Couples: {couples_count}"
                    f"{Colors.RESET}"
                )
                last_status = status
                last_status_time = now
            if current >= account_count:
                break
    except KeyboardInterrupt:
        print_warning("Generation interrupted by user!")
        settings.EXIT_FLAG = True

    for t in threads:
        t.join(timeout=5)

    elapsed = time.time() - start_time
    speed   = settings.SUCCESS_COUNTER / elapsed if elapsed > 0 else 0

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{get_random_color()}{Colors.BRIGHT}🎉 Generation complete!{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}📊 Generated:  {settings.SUCCESS_COUNTER}/{account_count}{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}💎 Rare:       {settings.RARE_COUNTER}{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}💑 Couples:    {settings.COUPLES_COUNTER}{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}⏱️  Time:       {elapsed:.2f}s{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}⚡ Speed:      {speed:.2f} acc/s{Colors.RESET}")

    if is_ghost:
        print(f"{Fore.LIGHTMAGENTA_EX}{Colors.BRIGHT}📁 GHOST accounts:  {format_project_path(settings.GHOST_ACCOUNTS_FOLDER)}{Colors.RESET}")
        print(f"{Fore.LIGHTMAGENTA_EX}{Colors.BRIGHT}💎 Rare GHOST:      {format_project_path(settings.GHOST_RARE_FOLDER)}{Colors.RESET}")
        print(f"{Fore.LIGHTMAGENTA_EX}{Colors.BRIGHT}💑 Couples GHOST:   {format_project_path(settings.GHOST_COUPLES_FOLDER)}{Colors.RESET}")
    else:
        print(f"{get_random_color()}{Colors.BRIGHT}📁 Accounts:        {format_project_path(settings.ACCOUNTS_FOLDER)}{Colors.RESET}")
        print(f"{get_random_color()}{Colors.BRIGHT}💎 Rare accounts:   {format_project_path(settings.RARE_ACCOUNTS_FOLDER)}{Colors.RESET}")
        print(f"{get_random_color()}{Colors.BRIGHT}💑 Couples:         {format_project_path(settings.COUPLES_ACCOUNTS_FOLDER)}{Colors.RESET}")
        print(f"{get_random_color()}{Colors.BRIGHT}🔐 JWT tokens:      {format_project_path(settings.TOKENS_FOLDER)}{Colors.RESET}")

    wait_for_enter()


# ── View Saved Accounts ───────────────────────────────────────────────────────

def view_saved_accounts() -> None:
    clear_screen()
    display_banner()
    print(f"{get_random_color()}{Colors.BRIGHT}📁 Saved Accounts{Colors.RESET}")

    account_files: list[str] = []
    if os.path.exists(settings.ACCOUNTS_FOLDER):
        account_files.extend(
            os.path.join(settings.ACCOUNTS_FOLDER, f)
            for f in os.listdir(settings.ACCOUNTS_FOLDER)
            if f.endswith(".json")
        )

    ghost_file = os.path.join(settings.GHOST_ACCOUNTS_FOLDER, "ghost.json")
    if os.path.exists(ghost_file):
        account_files.append(ghost_file)

    if not account_files:
        print(f"\n{Fore.YELLOW}{Colors.BRIGHT}📭 No saved accounts found.{Colors.RESET}")
        wait_for_enter()
        return

    total = 0
    for filepath in account_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                accounts = json.load(f)
            print(
                f"\n{get_random_color()}{Colors.BRIGHT}"
                f"📄 {os.path.basename(filepath)}: {len(accounts)} account(s){Colors.RESET}"
            )
            total += len(accounts)
        except Exception as e:
            print_error(f"Error reading {filepath}: {e}")

    print(f"\n{get_random_color()}{Colors.BRIGHT}📊 Total: {total} account(s){Colors.RESET}")
    wait_for_enter()


# ── Check Alive Proxies ───────────────────────────────────────────────────────

def check_alive_proxies_flow() -> None:
    clear_screen()
    display_banner()
    print(f"{get_random_color()}{Colors.BRIGHT}🌐 Check Alive Proxies{Colors.RESET}")

    proxy_count, invalid_proxy_count, proxy_file = refresh_proxy_pool()
    if proxy_count == 0 and invalid_proxy_count == 0:
        print_warning(f"No proxies found in {format_project_path(proxy_file)}")
        wait_for_enter()
        return

    workers = min(50, max(1, proxy_count))
    print(f"{get_random_color()}{Colors.BRIGHT}📄 Source:     {format_project_path(proxy_file)}{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}🎯 Proxies:    {proxy_count}{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}🧵 Threads:    {workers}{Colors.RESET}")
    print(f"{get_random_color()}{Colors.BRIGHT}⏱️ Timeout:    {PROXY_TEST_TIMEOUT}s each{Colors.RESET}")
    if invalid_proxy_count:
        print_warning(f"{invalid_proxy_count} invalid proxy line(s) will move offline.")
    print()

    def on_result(result, done: int, total: int) -> None:
        status = f"{done}/{total}"
        elapsed = f"{result.elapsed:.1f}s"
        if result.is_alive:
            print_success(f"[{status}] Alive {result.proxy.label} ({result.message}, {elapsed})")
        else:
            print_warning(f"[{status}] Dead {result.proxy.label} ({result.message}, {elapsed})")

    summary = check_proxy_pool(on_result=on_result, max_workers=workers)

    print(f"\n{get_random_color()}{Colors.BRIGHT}✅ Alive kept:   {len(summary.alive)} -> {format_project_path(summary.proxy_file)}{Colors.RESET}")
    print(f"{Fore.YELLOW}{Colors.BRIGHT}⚠️ Dead moved:   {len(summary.dead) + len(summary.invalid_lines)} -> {format_project_path(summary.offline_file)}{Colors.RESET}")
    print_success("Proxy pool refreshed. Generation will rotate alive proxies only.")
    wait_for_enter()


# ── About ─────────────────────────────────────────────────────────────────────

def about_section() -> None:
    clear_screen()
    display_banner()
    print(f"{get_random_color()}{Colors.BRIGHT}ℹ️   About TSun FF Guest Generator{Colors.RESET}")

    features = [
        "Multi-region Free Fire guest account generation",
        "GHOST Mode for special alternate-endpoint accounts",
        "Automatic JWT token extraction and storage",
        "Multi-threaded generation with configurable thread count",
        "Single or bulk proxy rotation from proxies.txt",
        "Alive proxy checker with offline proxy cleanup",
        "Rare account detection with configurable rarity scoring",
        "Couples account matching across threads",
        "Thread-safe atomic JSON storage",
    ]
    print(f"\n{get_random_color()}{Colors.BRIGHT}✨ Features:{Colors.RESET}")
    for feat in features:
        print(f"  {get_random_color()}• {feat}{Colors.RESET}")

    print(f"\n{get_random_color()}{Colors.BRIGHT}📁 Storage Locations:{Colors.RESET}")
    locations = [
        ("Accounts",       settings.ACCOUNTS_FOLDER),
        ("JWT Tokens",     settings.TOKENS_FOLDER),
        ("Rare Accounts",  settings.RARE_ACCOUNTS_FOLDER),
        ("Couples",        settings.COUPLES_ACCOUNTS_FOLDER),
        ("GHOST Accounts", settings.GHOST_ACCOUNTS_FOLDER),
    ]
    for label, path in locations:
        print(f"  {get_random_color()}• {label}: {format_project_path(path)}{Colors.RESET}")

    print(f"\n{get_random_color()}{Colors.BRIGHT}⚠️   Disclaimer:{Colors.RESET}")
    print(f"  {get_random_color()}This tool is for educational purposes only.{Colors.RESET}")
    print(f"  {get_random_color()}Use at your own risk.{Colors.RESET}")
    wait_for_enter()


# ── Main Menu ─────────────────────────────────────────────────────────────────

def main_menu() -> None:
    while True:
        clear_screen()
        display_banner()

        print(f"{get_random_color()}{Colors.BRIGHT}🎮 TSun FF Guest Generator{Colors.RESET}")
        print(f"\n{get_random_color()}{Colors.BRIGHT}📋 Options:{Colors.RESET}")
        print(f"  {get_random_color()}1) Generate Accounts{Colors.RESET}")
        print(f"  {get_random_color()}2) View Saved Accounts{Colors.RESET}")
        print(f"  {get_random_color()}3) Check Alive Proxies{Colors.RESET}")
        print(f"  {get_random_color()}4) About{Colors.RESET}")
        print(f"  {get_random_color()}0) {Fore.RED}Exit{Colors.RESET}")

        try:
            choice = input(f"\n{get_random_color()}{Colors.BRIGHT}🎯 Choose option: {Colors.RESET}").strip()
            if choice == "1":
                generate_accounts_flow()
            elif choice == "2":
                view_saved_accounts()
            elif choice == "3":
                check_alive_proxies_flow()
            elif choice == "4":
                about_section()
            elif choice == "0":
                print(f"\n{get_random_color()}{Colors.BRIGHT}👋 Goodbye!{Colors.RESET}")
                sys.exit(0)
            else:
                print_error("Invalid option. Choose 1, 2, 3, 4, or 0.")
                time.sleep(1)
        except KeyboardInterrupt:
            safe_exit()


# ── Prompt helpers ────────────────────────────────────────────────────────────

def _prompt_int(label: str, min_val: int = 1) -> int:
    while True:
        try:
            val = int(input(f"\n{get_random_color()}{Colors.BRIGHT}{label}: {Colors.RESET}"))
            if val >= min_val:
                return val
            print_error(f"Please enter a number >= {min_val}.")
        except ValueError:
            print_error("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            safe_exit()


def _prompt_str(label: str) -> str:
    while True:
        val = input(f"\n{get_random_color()}{Colors.BRIGHT}{label}: {Colors.RESET}").strip()
        if val:
            return val
        print_error("This field cannot be empty.")


def _prompt_yes_no(label: str) -> bool:
    while True:
        try:
            value = input(f"\n{get_random_color()}{Colors.BRIGHT}{label}: {Colors.RESET}").strip().lower()
            if value in ("y", "yes"):
                return True
            if value in ("n", "no"):
                return False
            print_error("Please enter y or n.")
        except KeyboardInterrupt:
            safe_exit()
