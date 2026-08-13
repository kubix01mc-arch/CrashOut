# Crash Out — Browser / WiFi multiplayer

Desktop window and terminal modes are unchanged (`python play.py`).

## Setup (once)

```bash
python -m pip install -r requirements-browser.txt
```

## Host a game

```bash
python play.py browser
```

or:

```bash
python crash_out_browser.py
```

- On this PC: open the URL printed (usually `http://127.0.0.1:8765`)
- On phones/laptops on the **same WiFi**: open `http://<host-lan-ip>:8765`
- Host clicks **Create room**, shares the room code; others **Join**

## Flow

Lobby → Card Lab (each player crafts privately) → Play (only your hand is shown) → Game over

Rules come from the same `CrashOut_Resources.py` engine as the desktop game.
