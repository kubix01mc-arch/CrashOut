#!/usr/bin/env python3
"""Crash Out launcher — choose terminal or window play."""

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
    print()
    while True:
        raw = input("Choice (1-2) [1]: ").strip() or "1"
        if raw in ("1", "2"):
            return raw
        print("  Enter 1 or 2.")


def main() -> None:
    # Optional CLI: python play.py window | terminal
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
        print(f"Unknown mode '{sys.argv[1]}'. Use: window | terminal")
        sys.exit(1)

    choice = pick_mode()
    if choice == "1":
        from crash_out_window import main as window_main

        window_main()
    else:
        from crash_out import main as terminal_main

        terminal_main()


if __name__ == "__main__":
    main()
