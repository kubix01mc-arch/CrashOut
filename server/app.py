"""FastAPI HTTP + WebSocket host for Crash Out browser multiplayer."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.session import MatchSession

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

app = FastAPI(title="Crash Out Browser")
rooms: dict[str, MatchSession] = {}
# room_code -> set of websockets
subscribers: dict[str, set[WebSocket]] = {}


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


@app.get("/api/host-info")
def host_info() -> dict[str, Any]:
    return {"lan_ip": lan_ip(), "hint": "Others on WiFi open http://<lan_ip>:8765"}


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
                    rooms[room.code] = room
                    room_code = room.code
                    subscribers.setdefault(room.code, set()).add(websocket)
                    name = str(msg.get("name") or "Host")
                    seat = room.join(name, preferred_seat=0)
                    token = seat.token
                    room.host_token = token
                    # Creator is host
                    websocket.player_token = token  # type: ignore[attr-defined]
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
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        if room_code and room_code in subscribers:
            subscribers[room_code].discard(websocket)
