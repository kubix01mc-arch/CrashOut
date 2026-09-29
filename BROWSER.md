# Crash Out — Browser (hotseat-style + WiFi rooms)

Desktop window/terminal modes are unchanged (`python play.py`).

## Setup (once)

```bash
python -m pip install -r requirements-browser.txt
```

## Run

```bash
python play.py browser
```

Same setup as window hotseat: match size (1 vs bot / 2–4 players), HP, PP, deck size.

+- **Host room** — creates a room with those settings; share the code
+- **Join** — enter a room code on the same WiFi
+- Vs bot (match size 1) goes straight into Card Lab

Open `http://127.0.0.1:8765` locally, or `http://<lan-ip>:8765` from phones on WiFi.
