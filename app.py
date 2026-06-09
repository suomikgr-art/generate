#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║         TSun FF Guest Generator                      ║
║         Credits: TSun × Kittens                      ║
║         For educational purposes only.               ║
╚══════════════════════════════════════════════════════╝
Entry point — installs missing dependencies, then launches the main menu.
"""

from __future__ import annotations

import importlib
import signal
import subprocess
import sys


# ── Dependency bootstrap ──────────────────────────────────────────────────────

_REQUIRED: dict[str, str] = {
    "requests":  "requests",
    "Crypto":    "pycryptodome",
    "colorama":  "colorama",
    "urllib3":   "urllib3",
    "psutil":    "psutil",
    "google.protobuf": "protobuf",
    "aiohttp":   "aiohttp",
}


def install_requirements() -> bool:
    """Ensure all required packages are present; install any that are missing."""
    print("🔍 Checking required packages...")
    all_ok = True
    for module, package in _REQUIRED.items():
        try:
            importlib.import_module(module)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ⚠️  Installing {package}...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", package],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"  ✅ {package} installed")
            except subprocess.CalledProcessError:
                print(f"  ❌ Failed to install {package}")
                all_ok = False
    return all_ok


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not install_requirements():
        sys.exit(1)

    import urllib3
    from urllib3.exceptions import InsecureRequestWarning
    urllib3.disable_warnings(InsecureRequestWarning)

    from ui.display import safe_exit
    from ui.menus import main_menu

    signal.signal(signal.SIGINT,  safe_exit)
    signal.signal(signal.SIGTERM, safe_exit)

    try:
        main_menu()
    except KeyboardInterrupt:
        safe_exit()
    except Exception as exc:
        import time, os
        from colorama import Fore, Style
        print(f"{Fore.RED}{Style.BRIGHT}❌ Unexpected error: {exc}{Style.RESET_ALL}")
        time.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)
