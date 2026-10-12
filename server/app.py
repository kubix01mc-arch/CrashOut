"""FastAPI HTTP + WebSocket host for Crash Out browser multiplayer."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from CrashOut_Resources import (
    DECK_SIZE,
    DEFAULT_POWER_POINTS,
    DEFAULT_STARTING_HP,
    HP_MAX,
    HP_MIN,
    MatchSettings,
    PLAYER_COUNT_MAX,
    clamp_deck_size,
)
from crash_out_pixel_bg import wallpaper_png_bytes
from crash_out_themes import (
    DEFAULT_FONT_PATH,
    active_theme,
    apply_theme_by_name,
    randomize_theme,
    reset_theme,
    restore_theme_preference,
    theme_names,
    theme_to_dict,
)
from server.session import MatchSession

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

app = FastAPI(title="Crash Out Browser")
rooms: dict[str, MatchSession] = {}
# room_code -> set of websockets
subscribers: dict[str, set[WebSocket]] = {}


@app.on_event("startup")
def _on_startup() -> None:
    restore_theme_preference()


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


@app.get("/api/host-info")
def host_info() -> dict[str, Any]:
    return {
        "lan_ip": lan_ip(),
        "hint": "Players connect to this server address and join with the six-digit code.",
    }


def _theme_payload() -> dict[str, Any]:
    theme = active_theme()
    return {
        "theme": theme_to_dict(theme),
        "names": theme_names(),
    }


@app.get("/api/theme")
def get_theme() -> dict[str, Any]:
    return _theme_payload()


@app.post("/api/theme")
def post_theme(body: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    action = str(body.get("action") or "").strip().lower()
    if action == "random":
        randomize_theme()
    elif action == "reset":
        reset_theme()
    elif action == "pick":
        apply_theme_by_name(str(body.get("name") or ""))
    return _theme_payload()


@app.get("/api/wallpaper")
def wallpaper(w: int = 960, h: int = 700, tint: str | None = None) -> Response:
    theme = active_theme()
    try:
        png = wallpaper_png_bytes(
            theme, min(960, max(64, w)), min(540, max(64, h)), tint=tint
        )
    except Exception:
        return Response(status_code=204)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/font")
def font_file() -> FileResponse:
    path = active_theme().font_path or DEFAULT_FONT_PATH
    if path is None or not Path(path).exists():
        path = DEFAULT_FONT_PATH
    return FileResponse(path, media_type="font/ttf")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


if WEB.exists():
    app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


async def _broadcast(code: str) -> None:
    room = rooms.get(code)
    if room is None:
        return
    dead: list[WebSocket] = []
    for ws in list(subscribers.get(code, set())):
        token = getattr(ws, "player_token", None)
        try:
            await ws.send_json({"type": "state", "state": room.view_for(token)})
        except Exception:
            dead.append(ws)
    for ws in dead:
        subscribers.get(code, set()).discard(ws)


async def _run_bot_turns(code: str) -> None:
    room = rooms.get(code)
    if room is None:
        return
    safety = 0
    while room.bot_should_act() and safety < 24:
        safety += 1
        await asyncio.sleep(0.65)
        room.run_one_bot_turn()
        await _broadcast(code)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    room_code: str | None = None
    token: str | None = None
    try:
        while True:
            msg = await websocket.receive_json()
            action = str(msg.get("action") or "")
            try:
                if action == "create":
                    room = MatchSession()
                    while room.code in rooms:
                        room = MatchSession()
                    player_count = int(msg.get("player_count") or 2)
                    vs_bot = bool(msg.get("vs_bot")) or player_count == 1
                    if vs_bot:
                        player_count = 1
                    starting_hp = int(msg.get("starting_hp") or DEFAULT_STARTING_HP)
                    starting_hp = max(HP_MIN, min(HP_MAX, starting_hp))
                    power_points = int(msg.get("power_points") or DEFAULT_POWER_POINTS)
                    deck_size = clamp_deck_size(int(msg.get("deck_size") or DECK_SIZE))
                    if player_count < 1:
                        player_count = 1
                    if player_count > PLAYER_COUNT_MAX:
                        player_count = PLAYER_COUNT_MAX
                    room.settings = MatchSettings(
                        player_count,
                        starting_hp,
                        power_points,
                        deck_size,
                    )
                    rooms[room.code] = room
                    room_code = room.code
                    subscribers.setdefault(room.code, set()).add(websocket)
                    name = str(msg.get("name") or "Host")
                    seat = room.join(name, preferred_seat=0)
                    token = seat.token
                    room.host_token = token
                    websocket.player_token = token  # type: ignore[attr-defined]
                    # Vs bot: skip waiting — go straight into Card Lab like window mode.
                    if room.vs_bot:
                        room.start_craft(room.host_token)
                    await websocket.send_json(
                        {
                            "type": "joined",
                            "token": token,
                            "host_token": room.host_token,
                            "seat": seat.seat,
                            "code": room.code,
                            "state": room.view_for(token),
                        }
                    )
                    await _broadcast(room.code)
                    continue

                if action == "join":
                    code = str(msg.get("code") or "").strip().upper()
                    room = rooms.get(code)
                    if room is None:
                        raise ValueError("Room not found. Check the code.")
                    if room.vs_bot:
                        raise RuntimeError("That room is vs bot — create your own.")
                    room_code = code
                    subscribers.setdefault(code, set()).add(websocket)
                    seat = room.join(str(msg.get("name") or "Player"))
                    token = seat.token
                    websocket.player_token = token  # type: ignore[attr-defined]
                    await websocket.send_json(
                        {
                            "type": "joined",
                            "token": token,
                            "host_token": None,
                            "seat": seat.seat,
                            "code": room.code,
                            "state": room.view_for(token),
                        }
                    )
                    await _broadcast(code)
                    continue

                if room_code is None or room_code not in rooms:
                    raise RuntimeError("Join or create a room first.")
                room = rooms[room_code]
                token = token or getattr(websocket, "player_token", None)

                if action == "set_settings":
                    room.set_settings(
                        player_count=int(msg["player_count"]),
                        starting_hp=int(msg["starting_hp"]),
                        power_points=int(msg["power_points"]),
                        deck_size=int(msg["deck_size"]),
                        host_token=str(msg.get("host_token") or ""),
                    )
                elif action == "start_craft":
                    room.start_craft(str(msg.get("host_token") or ""))
                elif action == "craft":
                    room.craft_next(
                        str(token),
                        damage=int(msg.get("damage") or 0),
                        steals=bool(msg.get("steals")),
                        heavy_hit=bool(msg.get("heavy_hit")),
                        shields=bool(msg.get("shields")),
                        poisons=bool(msg.get("poisons")),
                        exordia=bool(msg.get("exordia")),
                        cloak=bool(msg.get("cloak")),
                        lava=bool(msg.get("lava")),
                        joker=bool(msg.get("joker")),
                        reaper=bool(msg.get("reaper")),
                        vampire=bool(msg.get("vampire")),
                        cure=bool(msg.get("cure")),
                    )
                elif action == "finish_craft":
                    room.finish_craft(str(token))
                elif action == "play_card":
                    room.play_card(str(token), int(msg["card_id"]))
                elif action == "choose_target":
                    room.choose_target(str(token), int(msg["target"]))
                elif action == "cancel_pending":
                    room.cancel_pending(str(token))
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                else:
                    raise ValueError(f"Unknown action: {action}")

                await _broadcast(room_code)
                if action in ("finish_craft", "choose_target"):
                    await _run_bot_turns(room_code)
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        if room_code and room_code in subscribers:
            subscribers[room_code].discard(websocket)
