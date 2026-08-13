#!/usr/bin/env python3
"""Crash Out launcher — choose terminal, window, or browser (WiFi) play."""

from __future__ import annotations

import sys


def pick_mode() -> str:
    print()
    print("=" * 52)
    print("  CRASH OUT — Launch")
    print("=" * 52)
    print()
    print("How do you want to play?")
    print("  1) Window (graphical)")
    print("  2) Terminal")
    print("  3) Browser / WiFi multiplayer")
    print()
    while True:
        raw = input("Choice (1-3) [1]: ").strip() or "1"
        if raw in ("1", "2", "3"):
            return raw
        print("  Enter 1, 2, or 3.")


def main() -> None:
    # Optional CLI: python play.py window | terminal | browser
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().lower()
        if arg in ("window", "gui", "1", "-w"):
            from crash_out_window import main as window_main

            window_main()
            return
        if arg in ("terminal", "cli", "2", "-t"):
            from crash_out import main as terminal_main

            terminal_main()
            return
        if arg in ("browser", "web", "wifi", "3", "-b"):
            from crash_out_browser import main as browser_main

            browser_main()
            return
        print(f"Unknown mode '{sys.argv[1]}'. Use: window | terminal | browser")
        sys.exit(1)

    choice = pick_mode()
    if choice == "1":
        from crash_out_window import main as window_main

        window_main()
    elif choice == "2":
        from crash_out import main as terminal_main

        terminal_main()
    else:
        from crash_out_browser import main as browser_main

        browser_main()


if __name__ == "__main__":
    main()
