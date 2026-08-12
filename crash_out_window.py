#!/usr/bin/env python3
"""Crash Out — window (tkinter) UI."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageTk

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from CrashOut_Resources import (
    ARCHETYPE_UNIQUE_LIMIT,
    BOT_NAME,
    DEFAULT_POWER_POINTS,
    DEFAULT_STARTING_HP,
    DECK_SIZE,
    DECK_SIZE_MAX,
    DECK_SIZE_MIN,
    FIFTH_CARD_HEAL,
    HP_MAX,
    HP_MIN,
    MatchSettings,
    PP_MAX,
    PP_MIN,
    STEAL_PP_COST,
    TURN_DELAY_MS,
    ActiveBorrow,
    Card,
    Player,
    allows_duplicate_archetypes,
    archetype_taken,
    bot_choose_play,
    can_add_heavy_hit_card,
    can_add_steal_card,
    can_craft_steal,
    card_is_cooling,
    check_winner,
    clamp_deck_size,
    craft_card,
    deck_has_heavy_hit,
    deck_has_steal,
    describe_target,
    make_bot_deck,
    make_mercy_card,
    make_players_from_mixed_decks,
    make_solo_players,
    mark_card_played,
    name_for_split,
    next_alive_index,
    resolve_card,
    resolve_steal,
    return_expired_borrows,
    stat_budget,
    tick_turn_cooldowns,
)
from crash_out_themes import (
    active_theme,
    randomize_theme,
    reset_theme,
)
from crash_out_pixel_bg import generate_theme_wallpaper

# Playing-card style buttons: width:height = 5:7
CARD_ASPECT = 7 / 5
CARD_MIN_W = 48
CARD_MAX_W = 200
CARD_GAP_MIN = 6
TARGET_MIN = 100
TARGET_MAX = 200
LOG_CLOSE_SIZE = 40
PREVIEW_CARD_W = 168
DECK_MINI_W = 110
BOT_ICON_PATH = Path(__file__).resolve().parent / "assets" / "bot_icon.png"


def _theme():
    return active_theme()


def _font_family() -> str:
    return _theme().font_family


def card_size_for_area(
    area_w: int,
    area_h: int,
    num_cards: int,
    *,
    pad_x: int = 12,
    pad_y: int = 12,
) -> tuple[int, int]:
    """Fit num_cards in area while keeping 5:7 aspect ratio."""
    if num_cards <= 0 or area_w < CARD_MIN_W or area_h < CARD_MIN_W:
        return CARD_MIN_W, int(CARD_MIN_W * CARD_ASPECT)

    gap = max(CARD_GAP_MIN, area_w // 80)
    avail_w = max(CARD_MIN_W, area_w - pad_x * 2 - gap * max(0, num_cards - 1))
    avail_h = max(CARD_MIN_W, area_h - pad_y * 2)

    card_w = min(CARD_MAX_W, avail_w // num_cards)
    card_h = int(card_w * CARD_ASPECT)
    if card_h > avail_h:
        card_h = avail_h
        card_w = int(card_h / CARD_ASPECT)

    card_w = max(CARD_MIN_W, min(CARD_MAX_W, card_w))
    card_h = int(card_w * CARD_ASPECT)
    if card_h > avail_h:
        card_h = max(int(CARD_MIN_W * CARD_ASPECT), avail_h)
        card_w = int(card_h / CARD_ASPECT)
    return card_w, card_h


def target_size_for_area(area_w: int, area_h: int, num_targets: int) -> tuple[int, int]:
    """Square target buttons that fit in the overlay panel."""
    if num_targets <= 0:
        return TARGET_MIN, CARD_GAP_MIN
    gap = max(CARD_GAP_MIN, area_w // 60)
    avail_w = max(TARGET_MIN, area_w - 48 - gap * max(0, num_targets - 1))
    avail_h = max(TARGET_MIN, area_h - 80)
    size = min(TARGET_MAX, avail_w // num_targets, avail_h)
    return max(TARGET_MIN, size), gap


def _shift_hex(color: str, delta: int) -> str:
    raw = color.lstrip("#")
    rgb = [max(0, min(255, int(raw[i : i + 2], 16) + delta)) for i in (0, 2, 4)]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _pixel_scale(size: int) -> int:
    return max(2, size // 28)


def _mc_font_size(size: int) -> int:
    """Minecraft bitmap fonts stay crisp on an 8px grid."""
    return max(8, int(round(size / 8) * 8))


def _draw_pixel_panel(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    fill: str,
    accent: str,
    scale: int,
) -> None:
    """Minecraft-style beveled panel with 1-pixel corner cuts."""
    s = scale
    highlight = _shift_hex(fill, 38)
    shadow = _shift_hex(fill, -40)
    outline = _shift_hex(accent, -50)

    canvas.create_rectangle(
        x1 + s, y1, x2 - s, y2, fill=fill, outline="", width=0
    )
    canvas.create_rectangle(
        x1, y1 + s, x2, y2 - s, fill=fill, outline="", width=0
    )

    canvas.create_rectangle(x1 + s, y1, x2 - s, y1 + s, fill=outline, outline="", width=0)
    canvas.create_rectangle(x1 + s, y2 - s, x2 - s, y2, fill=outline, outline="", width=0)
    canvas.create_rectangle(x1, y1 + s, x1 + s, y2 - s, fill=outline, outline="", width=0)
    canvas.create_rectangle(x2 - s, y1 + s, x2, y2 - s, fill=outline, outline="", width=0)

    canvas.create_rectangle(
        x1 + s, y1 + s, x2 - s, y1 + 2 * s, fill=highlight, outline="", width=0
    )
    canvas.create_rectangle(
        x1 + s, y1 + s, x1 + 2 * s, y2 - s, fill=highlight, outline="", width=0
    )
    canvas.create_rectangle(
        x1 + s, y2 - 2 * s, x2 - s, y2 - s, fill=shadow, outline="", width=0
    )
    canvas.create_rectangle(
        x2 - 2 * s, y1 + s, x2 - s, y2 - s, fill=shadow, outline="", width=0
    )

    inner = 3 * s
    ix1, iy1, ix2, iy2 = x1 + inner, y1 + inner, x2 - inner, y2 - inner
    if ix2 - ix1 > 4 * s and iy2 - iy1 > 4 * s:
        canvas.create_rectangle(
            ix1 + s, iy1, ix2 - s, iy1 + s, fill=accent, outline="", width=0
        )
        canvas.create_rectangle(
            ix1 + s, iy2 - s, ix2 - s, iy2, fill=accent, outline="", width=0
        )
        canvas.create_rectangle(
            ix1, iy1 + s, ix1 + s, iy2 - s, fill=accent, outline="", width=0
        )
        canvas.create_rectangle(
            ix2 - s, iy1 + s, ix2, iy2 - s, fill=accent, outline="", width=0
        )


def _draw_neon_card(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, fill: str, accent: str, scale: int
) -> None:
    s = max(2, scale)
    canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")
    for inset, color in ((0, accent), (s, _shift_hex(accent, 40)), (2 * s, _shift_hex(accent, -35))):
        canvas.create_rectangle(
            x1 + inset, y1 + inset, x2 - inset, y2 - inset, outline=color, width=s
        )
    arm = 5 * s
    for px, py, dx, dy in (
        (x1 + s, y1 + s, 1, 1),
        (x2 - s, y1 + s, -1, 1),
        (x1 + s, y2 - s, 1, -1),
        (x2 - s, y2 - s, -1, -1),
    ):
        canvas.create_line(px, py, px + dx * arm, py, fill=accent, width=s)
        canvas.create_line(px, py, px, py + dy * arm, fill=accent, width=s)


def _draw_stone_card(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, fill: str, accent: str, scale: int
) -> None:
    s = max(2, scale)
    canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=_shift_hex(accent, -40), width=s)
    row_h = max(3, 3 * s)
    row = 0
    y = y1 + s
    while y < y2 - s:
        offset = (row % 2) * (4 * s)
        x = x1 + s + offset
        while x < x2 - s:
            bw = min(7 * s, x2 - s - x)
            bh = min(row_h - s, y2 - s - y)
            brick = _shift_hex(fill, 10 if row % 2 else -10)
            canvas.create_rectangle(x, y, x + bw, y + bh, fill=brick, outline=_shift_hex(accent, -55))
            x += 8 * s
        y += row_h
        row += 1


def _draw_ice_card(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, fill: str, accent: str, scale: int
) -> None:
    s = max(2, scale)
    canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=accent, width=s)
    frost = _shift_hex(accent, 50)
    step = max(2, 3 * s)
    d = y2 - y1
    i = x1 - d
    while i < x2 + d:
        canvas.create_line(i, y1 + s, i + d, y2 - s, fill=frost, width=max(1, s // 2))
        i += step
    canvas.create_rectangle(x1 + s, y1 + s, x2 - s, y1 + 2 * s, fill="#ffffff", outline="")


def _draw_lava_card(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, fill: str, accent: str, scale: int
) -> None:
    s = max(2, scale)
    canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=_shift_hex(accent, -30), width=s)
    w, h = x2 - x1, y2 - y1
    cracks = (
        (x1 + 3 * s, y1 + 4 * s, x1 + w // 2, y1 + h // 3),
        (x1 + w // 2, y1 + h // 3, x2 - 4 * s, y2 - 5 * s),
        (x1 + 5 * s, y2 - 6 * s, x2 - 6 * s, y1 + h // 2),
        (x1 + w // 3, y1 + 6 * s, x1 + 2 * w // 3, y2 - 4 * s),
    )
    for x_a, y_a, x_b, y_b in cracks:
        canvas.create_line(x_a, y_a, x_b, y_b, fill=accent, width=max(1, s))
        canvas.create_line(x_a + s, y_a, x_b + s, y_b, fill=_shift_hex(accent, 35), width=max(1, s // 2))


def _draw_arcade_card(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, fill: str, accent: str, scale: int
) -> None:
    s = max(2, scale)
    stripe = 2 * s
    row = 0
    y = y1
    while y < y2:
        color = _shift_hex(fill, 14 if row % 2 else -14)
        canvas.create_rectangle(x1, y, x2, min(y + stripe, y2), fill=color, outline="")
        y += stripe
        row += 1
    canvas.create_rectangle(x1, y1, x2, y2, outline=accent, width=2 * s)
    dot = 2 * s
    for px, py in ((x1 + dot, y1 + dot), (x2 - dot, y1 + dot), (x1 + dot, y2 - dot), (x2 - dot, y2 - dot)):
        canvas.create_rectangle(px - dot, py - dot, px + dot, py + dot, fill=accent, outline="")


def _draw_gold_card(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, fill: str, accent: str, scale: int
) -> None:
    s = max(2, scale)
    canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=accent, width=2 * s)
    inset = 2 * s
    canvas.create_rectangle(
        x1 + inset, y1 + inset, x2 - inset, y2 - inset,
        outline=_shift_hex(accent, 25), width=s,
    )
    gem = 2 * s
    for px, py in ((x1 + 3 * s, y1 + 3 * s), (x2 - 3 * s, y1 + 3 * s), (x1 + 3 * s, y2 - 3 * s), (x2 - 3 * s, y2 - 3 * s)):
        canvas.create_rectangle(px - gem, py - gem, px + gem, py + gem, fill=accent, outline=_shift_hex(accent, 40))


def _draw_circuit_card(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, fill: str, accent: str, scale: int
) -> None:
    s = max(2, scale)
    canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=accent, width=s)
    step = max(3, 4 * s)
    dot = max(1, s)
    gx = x1 + 2 * s
    while gx < x2 - 2 * s:
        gy = y1 + 2 * s
        while gy < y2 - 2 * s:
            canvas.create_rectangle(gx, gy, gx + dot, gy + dot, fill=_shift_hex(accent, -15), outline="")
            gy += step
        gx += step
    mid = (y1 + y2) // 2
    canvas.create_line(x1 + 4 * s, mid, x2 - 4 * s, mid, fill=accent, width=s)
    canvas.create_line((x1 + x2) // 2, y1 + 4 * s, (x1 + x2) // 2, y2 - 4 * s, fill=accent, width=s)


def _draw_shadow_card(
    canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, fill: str, accent: str, scale: int
) -> None:
    s = max(2, scale)
    canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")
    inset = 2 * s
    canvas.create_rectangle(
        x1 + inset, y1 + inset, x2 - inset, y2 - inset, outline=accent, width=s
    )
    canvas.create_line(
        x1 + inset, y1 + inset + 3 * s, x2 - inset, y1 + inset + 3 * s,
        fill=_shift_hex(accent, -35), width=s,
    )


_CARD_FRAME_DRAWERS = {
    "pixel": _draw_pixel_panel,
    "neon": _draw_neon_card,
    "stone": _draw_stone_card,
    "ice": _draw_ice_card,
    "lava": _draw_lava_card,
    "arcade": _draw_arcade_card,
    "gold": _draw_gold_card,
    "circuit": _draw_circuit_card,
    "shadow": _draw_shadow_card,
}


def _draw_card_frame(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    fill: str,
    accent: str,
    scale: int,
) -> None:
    style = _theme().card_style
    drawer = _CARD_FRAME_DRAWERS.get(style, _draw_pixel_panel)
    drawer(canvas, x1, y1, x2, y2, fill, accent, scale)


class RoundedCardButton(tk.Canvas):
    """Clickable pixel-art card face (5:7 aspect ratio)."""

    def __init__(
        self,
        parent: tk.Misc,
        card: Card,
        *,
        command=None,
        disabled: bool = False,
        selected: bool = False,
        width: int = CARD_MIN_W,
        height: int | None = None,
    ) -> None:
        height = height or int(width * CARD_ASPECT)
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=_theme().screen_bg,
            highlightthickness=0,
            bd=0,
            cursor="arrow" if disabled or command is None else "hand2",
        )
        self.card = card
        self.command = command
        self.disabled = disabled
        self.selected = selected
        self._hover = False
        self._width = width
        self._height = height
        self._draw()
        if not disabled and command is not None:
            self.bind("<Button-1>", self._on_click)
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)

    def set_size(self, width: int, height: int) -> None:
        width = max(CARD_MIN_W, width)
        height = max(int(CARD_MIN_W * CARD_ASPECT), height)
        if width == self._width and height == self._height:
            return
        self._width = width
        self._height = height
        self.configure(width=width, height=height)
        self._draw(self._hover)

    def set_card(self, card: Card, *, disabled: bool | None = None) -> None:
        self.card = card
        if disabled is not None:
            self.disabled = disabled
            self.configure(cursor="arrow" if self.disabled or self.command is None else "hand2")
        self._draw(self._hover)

    def _font(self, ratio: float, minimum: int = 8) -> tuple[str, int, str]:
        size = _mc_font_size(max(minimum, int(min(self._width, self._height) * ratio)))
        return (_font_family(), size, "bold")

    def _font_regular(self, ratio: float, minimum: int = 8) -> tuple[str, int]:
        size = _mc_font_size(max(minimum, int(min(self._width, self._height) * ratio)))
        return (_font_family(), size)

    def _fill_colors(self) -> tuple[str, str, str]:
        art = _theme().cards
        if self.disabled:
            return art.disabled
        if self.selected:
            return art.selected
        if self.card.heal_any:
            return art.heal
        if self.card.heavy_hit:
            return art.heavy_hit
        if self.card.steals:
            return art.steal
        return art.normal

    def _draw(self, hover: bool = False) -> None:
        self.delete("all")
        fill, accent, text_color = self._fill_colors()
        if hover and not self.disabled:
            fill = _shift_hex(fill, 22)
        scale = _pixel_scale(self._width)
        pad = scale
        x1, y1 = pad, pad
        x2, y2 = self._width - pad, self._height - pad
        _draw_card_frame(self, x1, y1, x2, y2, fill, accent, scale)

        cx = self._width // 2
        title_y = y1 + 7 * scale
        stats_y = int(self._height * 0.54)
        detail_y = y2 - 6 * scale
        style = _theme().card_style
        div_x1 = x1 + 5 * scale
        div_x2 = x2 - 5 * scale
        if style not in ("shadow", "circuit"):
            divider_y1 = int(self._height * 0.30)
            divider_y2 = int(self._height * 0.76)
            self.create_rectangle(
                div_x1, divider_y1, div_x2, divider_y1 + scale, fill=accent, outline="", width=0
            )
            self.create_rectangle(
                div_x1, divider_y2, div_x2, divider_y2 + scale, fill=accent, outline="", width=0
            )
        elif style == "circuit":
            self.create_rectangle(
                div_x1, y1 + 5 * scale, div_x2, y1 + 5 * scale + max(1, scale // 2),
                fill=accent, outline="", width=0,
            )

        self.create_text(
            cx,
            title_y,
            text=self.card.name.upper(),
            fill=text_color,
            font=self._font(0.10, 8),
            width=self._width - 10 * scale,
            justify="center",
        )
        stats, detail = self.card.face_stats()
        if self.disabled:
            detail = "cooling down"
        elif self.card.is_borrowed:
            detail = "borrowed"

        self.create_text(
            cx,
            stats_y,
            text=stats,
            fill=accent,
            font=self._font(0.13, 8),
            justify="center",
        )
        self.create_text(
            cx,
            detail_y,
            text=detail,
            fill=text_color,
            font=self._font_regular(0.08, 8),
            width=self._width - 8 * scale,
            justify="center",
        )

    def _on_click(self, _event=None) -> None:
        if not self.disabled and self.command:
            self.command()

    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._draw(hover=True)

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._draw(hover=False)


class RoundedTargetButton(tk.Canvas):
    """Rounded-square button for choosing a target player."""

    def __init__(
        self,
        parent: tk.Misc,
        player: Player,
        subtitle: str,
        *,
        command,
        is_self: bool = False,
        bot_photo_getter=None,
        width: int = TARGET_MIN,
        height: int | None = None,
    ) -> None:
        height = height or width
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=_theme().target_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.player = player
        self.subtitle = subtitle
        self.command = command
        self.is_self = is_self
        self._bot_photo_getter = bot_photo_getter
        self._hover = False
        self._size = width
        self._bot_photo = None
        self._draw()
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    @staticmethod
    def _player_number(player: Player) -> str:
        if player.name.startswith("player-"):
            return player.name.split("-", 1)[1]
        return player.name

    def set_size(self, size: int) -> None:
        size = max(TARGET_MIN, size)
        if size == self._size:
            return
        self._size = size
        self.configure(width=size, height=size)
        self._draw(self._hover)

    def _colors(self, hover: bool) -> tuple[str, str, str]:
        theme = _theme()
        if self.is_self:
            fill, accent, text = theme.target_self
        else:
            fill, accent, text = theme.target_other
        if hover:
            fill = _shift_hex(fill, 22)
        return fill, accent, text

    def _draw_badge(self, cx: int, cy: int, accent: str, text_color: str) -> None:
        if self.player.is_bot and self._bot_photo_getter is not None:
            icon_size = max(32, int(self._size * 0.42))
            icon_size = (icon_size // 8) * 8
            photo = self._bot_photo_getter(icon_size)
            if photo is not None:
                self._bot_photo = photo
                self.create_image(cx, cy, image=photo)
                return
        number = self._player_number(self.player)
        self.create_text(
            cx,
            cy,
            text=number,
            fill=accent,
            font=(_font_family(), _mc_font_size(max(16, self._size // 3)), "bold"),
            justify="center",
        )

    def _draw(self, hover: bool = False) -> None:
        self.delete("all")
        fill, accent, text_color = self._colors(hover)
        s = self._size
        scale = _pixel_scale(s)
        pad = scale
        _draw_card_frame(self, pad, pad, s - pad, s - pad, fill, accent, scale)
        cx = s // 2
        self._draw_badge(cx, int(s * 0.34), accent, text_color)
        self.create_text(
            cx,
            int(s * 0.62),
            text=f"{self.player.hp}/{self.player.max_hp}",
            fill=accent,
            font=(_font_family(), _mc_font_size(max(8, s // 9)), "bold"),
            justify="center",
        )
        self.create_text(
            cx,
            int(s * 0.82),
            text=self.subtitle,
            fill=text_color,
            font=(_font_family(), _mc_font_size(max(8, s // 14))),
            width=s - pad * 6,
            justify="center",
        )

    def _on_click(self, _event=None) -> None:
        if self.command:
            self.command()

    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._draw(hover=True)

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._draw(hover=False)


HUD_CHIP_W = 152
HUD_CHIP_H = 72
ART_BTN_W = 200
ART_BTN_H = 52


class PixelCloseButton(tk.Canvas):
    """Small pixel-art X button for closing overlays."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        command=None,
        size: int = LOG_CLOSE_SIZE,
        bg: str | None = None,
    ) -> None:
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=bg if bg is not None else _theme().log_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.command = command
        self._hover = False
        self._size = size
        self._draw()
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _draw(self, hover: bool = False) -> None:
        self.delete("all")
        art = _theme().cards
        fill, accent, _text = art.heavy_hit
        if hover:
            fill = _shift_hex(fill, 28)
            accent = _shift_hex(accent, 20)
        s = max(2, self._size // 14)
        pad = s
        _draw_card_frame(self, pad, pad, self._size - pad, self._size - pad, fill, accent, s)
        # Pixel X made of thick diagonal bars
        m = self._size // 2
        arm = self._size // 2 - 3 * s
        thickness = max(2, s + 1)
        for dx in range(-thickness // 2, thickness // 2 + 1):
            self.create_line(
                m - arm + dx, m - arm, m + arm + dx, m + arm,
                fill=accent, width=s,
            )
            self.create_line(
                m + arm + dx, m - arm, m - arm + dx, m + arm,
                fill=accent, width=s,
            )

    def _on_click(self, _event=None) -> None:
        if self.command:
            self.command()

    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._draw(hover=True)

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._draw(hover=False)


class ThemedArtButton(tk.Canvas):
    """Action button drawn with the active theme's card-frame art."""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        *,
        command=None,
        width: int = ART_BTN_W,
        height: int = ART_BTN_H,
        palette: str = "normal",
        bg: str | None = None,
    ) -> None:
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=bg if bg is not None else _theme().screen_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._label = text
        self.command = command
        self._palette = palette
        self._hover = False
        self._width = width
        self._height = height
        self._draw()
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _colors(self, hover: bool) -> tuple[str, str, str]:
        art = _theme().cards
        mapping = {
            "normal": art.normal,
            "heal": art.heal,
            "heavy_hit": art.heavy_hit,
            "steal": art.steal,
            "selected": art.selected,
            "disabled": art.disabled,
        }
        fill, accent, text = mapping.get(self._palette, art.normal)
        if hover:
            fill = _shift_hex(fill, 22)
        return fill, accent, text

    def _draw(self, hover: bool = False) -> None:
        self.delete("all")
        fill, accent, text_color = self._colors(hover)
        scale = _pixel_scale(min(self._width, self._height * 2))
        pad = scale
        x1, y1 = pad, pad
        x2, y2 = self._width - pad, self._height - pad
        _draw_card_frame(self, x1, y1, x2, y2, fill, accent, scale)
        self.create_text(
            self._width // 2,
            self._height // 2,
            text=self._label.upper(),
            fill=text_color,
            font=(
                _font_family(),
                _mc_font_size(max(10, self._height // 3)),
                "bold",
            ),
            justify="center",
        )

    def _on_click(self, _event=None) -> None:
        if self.command:
            self.command()

    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._draw(hover=True)

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._draw(hover=False)


class PixelHudChip(tk.Canvas):
    """Pixel-art HP chip; the active player's panel is the turn indicator."""

    def __init__(
        self,
        parent: tk.Misc,
        player: Player,
        *,
        is_active: bool,
    ) -> None:
        super().__init__(
            parent,
            width=HUD_CHIP_W,
            height=HUD_CHIP_H,
            bg=_theme().screen_bg,
            highlightthickness=0,
            bd=0,
        )
        self.player = player
        self.is_active = is_active
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        theme = _theme()
        if not self.player.alive:
            fill, accent, text_color = theme.hud_dead
        elif self.is_active:
            fill, accent, text_color = theme.hud_active
        else:
            fill, accent, text_color = theme.hud_idle
        scale = 3
        _draw_pixel_panel(self, 0, 0, HUD_CHIP_W, HUD_CHIP_H, fill, accent, scale)
        cx = HUD_CHIP_W // 2
        name = self.player.name.upper()
        self.create_text(
            cx,
            22,
            text=name,
            fill=accent if self.is_active else text_color,
            font=(_font_family(), 8, "bold" if self.is_active else "normal"),
            justify="center",
        )
        hp_text = f"{self.player.hp}/{self.player.max_hp} HP" if self.player.alive else "OUT"
        self.create_text(
            cx,
            48,
            text=hp_text,
            fill=accent if self.player.alive else text_color,
            font=(_font_family(), 16, "bold"),
            justify="center",
        )


class CrashOutApp(tk.Tk):
    def __init__(self) -> None:
        reset_theme()
        super().__init__()
        self.title("Crash Out")
        self.geometry("920x700")
        self.minsize(480, 400)
        self._screen = "setup"
        self._play_banner = ""
        self._game_over_winner: str | None = None
        self._fullscreen = False
        self.bind("<F11>", self._toggle_fullscreen)

        self.settings: MatchSettings | None = None
        self.players: list[Player] = []
        self.crafted: list[Card] = []
        self.all_player_decks: list[list[Card]] = []
        self.crafting_player = 1
        self.craft_slot = 1
        self.active = 0
        self.pending_card: Card | None = None
        self.pending_target_idx: int | None = None
        self.starting_hp = DEFAULT_STARTING_HP
        self._busy = False
        self._borrows: list[ActiveBorrow] = []
        self._game_log: list[str] = []
        self.log: tk.Text | None = None
        self._card_faces: list[RoundedCardButton] = []
        self._hand_outer: tk.Frame | None = None
        self._overlay_host = tk.Frame(self, bg=_theme().screen_bg)
        self._target_overlay: tk.Canvas | None = None
        self._log_overlay: tk.Canvas | None = None
        self._log_panel: tk.Misc | None = None
        self._log_inner_id: int | None = None
        self._craft_scale: ttk.Scale | None = None
        self._target_row: tk.Frame | None = None
        self._target_buttons: list[RoundedTargetButton] = []
        self._bot_photo_cache: dict[int, tk.PhotoImage] = {}
        self.preview: RoundedCardButton | None = None
        self.preview_status: ttk.Label | None = None
        self.save_btn: ttk.Button | None = None
        self._theme_label: ttk.Label | None = None
        self._bg_photo: tk.PhotoImage | None = None
        self._root_bg_photo: tk.PhotoImage | None = None
        self._bg_tint: str | None = None
        self._ui_fill = False
        self._last_root_size = (0, 0)
        self._last_container_size = (0, 0)
        self._bg_resize_job: str | None = None
        self.bind("<Escape>", self._on_escape_overlay)

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self._apply_theme_styles()

        self._root_bg = tk.Label(self, bd=0, highlightthickness=0)
        self._root_bg.place(x=0, y=0, relwidth=1, relheight=1)
        self.container = tk.Canvas(self, highlightthickness=0, bd=0, bg=_theme().screen_bg)
        self.container.pack(fill="both", expand=True, padx=16, pady=16)
        self._ui = tk.Frame(self.container, bg=_theme().screen_bg)
        self._ui_win = self.container.create_window(0, 0, anchor="nw", window=self._ui)
        self.container.bind("<Configure>", self._on_container_configure)
        self.bind("<Configure>", self._on_root_configure)
        self._refresh_wallpapers()
        self.show_setup()

    def _apply_theme_styles(self) -> None:
        theme = _theme()
        self.configure(bg=theme.screen_bg)
        if hasattr(self, "container"):
            self.container.configure(bg=theme.screen_bg)
        if hasattr(self, "_ui"):
            self._ui.configure(bg=theme.screen_bg)
        if hasattr(self, "_overlay_host"):
            self._overlay_host.configure(bg=theme.screen_bg)
        if hasattr(self, "_root_bg"):
            self._refresh_wallpapers()
        self.style.configure(
            "Title.TLabel",
            font=(_font_family(), 22, "bold"),
            foreground=theme.title_fg,
            background=theme.screen_bg,
        )
        self.style.configure(
            "Body.TLabel",
            font=(_font_family(), 11),
            foreground=theme.body_fg,
            background=theme.screen_bg,
        )
        self.style.configure(
            "Log.TLabel",
            font=(_font_family(), 10),
            foreground=theme.log_fg,
            background=theme.log_bg,
        )
        self.style.configure("Accent.TButton", font=(_font_family(), 11, "bold"))
        self.style.configure(
            "SetupTitle.TLabel",
            font=(_font_family(), 32, "bold"),
            foreground=theme.title_fg,
            background=theme.screen_bg,
        )
        self.style.configure(
            "SetupBody.TLabel",
            font=(_font_family(), 16),
            foreground=theme.body_fg,
            background=theme.screen_bg,
        )
        self.style.configure(
            "Setup.TButton",
            font=(_font_family(), 16, "bold"),
            padding=(16, 8),
        )
        self.style.configure(
            "Setup.TCombobox",
            font=(_font_family(), 16),
        )
        self.style.configure(
            "Setup.TEntry",
            font=(_font_family(), 16),
        )
        self.style.configure(
            "Lab.TCheckbutton",
            font=(_font_family(), 16),
            background=theme.screen_bg,
            foreground=theme.body_fg,
        )
        self.style.configure(
            "Green.Horizontal.TScale",
            troughcolor=theme.scale_trough,
            background=theme.scale_fill,
            bordercolor=theme.scale_border,
            lightcolor=theme.scale_light,
            darkcolor=theme.scale_dark,
        )
        self.style.map(
            "Green.Horizontal.TScale",
            background=[("active", theme.scale_light), ("!disabled", theme.scale_fill)],
        )

    def _refresh_current_screen(self) -> None:
        if self._screen == "setup":
            self.show_setup()
        elif self._screen == "craft":
            self.show_craft()
        elif self._screen == "play":
            self.show_play(self._play_banner)
        elif self._screen == "game_over":
            self.show_game_over(self._game_over_winner)

    def _on_random_theme(self) -> None:
        theme = randomize_theme()
        self._apply_theme_styles()
        self._refresh_current_screen()
        if self._theme_label is not None and self._theme_label.winfo_exists():
            self._theme_label.configure(
                text=f"Theme: {theme.name} ({theme.card_style}) — {theme.font_family}"
            )

    def _on_reset_theme(self) -> None:
        theme = reset_theme()
        self._apply_theme_styles()
        self._refresh_current_screen()
        if self._theme_label is not None and self._theme_label.winfo_exists():
            self._theme_label.configure(text=f"Theme: {theme.name}")

    def _reset_game(self) -> None:
        """Clear match progress and return to setup; keep the active theme."""
        self._busy = False
        self.settings = None
        self.players = []
        self.crafted = []
        self.all_player_decks = []
        self.crafting_player = 1
        self.craft_slot = 1
        self.active = 0
        self.pending_card = None
        self.pending_target_idx = None
        self.starting_hp = DEFAULT_STARTING_HP
        self._borrows = []
        self._game_log = []
        self._play_banner = ""
        self._game_over_winner = None
        self.show_setup()

    def _toggle_fullscreen(self, _event: tk.Event | None = None) -> str:
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)
        return "break"

    def _raise_overlay_layer(self) -> None:
        self._overlay_host.place(relx=0, rely=0, relwidth=1, relheight=1)
        try:
            self.container.lower(self._overlay_host)
        except tk.TclError:
            pass
        tk.Misc.tkraise(self._overlay_host)

    def _set_screen_bg(self, color: str) -> None:
        self._bg_tint = color
        self.configure(bg=color)
        if hasattr(self, "container"):
            self.container.configure(bg=color)
        if hasattr(self, "_ui"):
            self._ui.configure(bg=color)
        if hasattr(self, "_overlay_host"):
            self._overlay_host.configure(bg=color)
        self._refresh_wallpapers(tint=color)

    def _on_root_configure(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        if event.width < 40 or event.height < 40:
            return
        size = (event.width, event.height)
        if size == self._last_root_size:
            return
        self._last_root_size = size
        self._refresh_root_wallpaper(event.width, event.height)

    def _on_container_configure(self, event: tk.Event) -> None:
        if event.widget is not self.container:
            return
        if event.width < 40 or event.height < 40:
            return
        size = (event.width, event.height)
        if size == self._last_container_size:
            self._layout_ui_window(event.width, event.height)
            return
        self._last_container_size = size
        if self._bg_resize_job is not None:
            try:
                self.after_cancel(self._bg_resize_job)
            except tk.TclError:
                pass
        self._bg_resize_job = self.after(
            40, lambda w=event.width, h=event.height: self._finish_container_resize(w, h)
        )

    def _finish_container_resize(self, width: int, height: int) -> None:
        self._bg_resize_job = None
        self._refresh_container_wallpaper(width, height)
        self._layout_ui_window(width, height)

    def _refresh_wallpapers(self, tint: str | None = None) -> None:
        if tint is not None:
            self._bg_tint = tint
        self.update_idletasks()
        rw = max(self.winfo_width(), 200)
        rh = max(self.winfo_height(), 200)
        self._refresh_root_wallpaper(rw, rh)
        if hasattr(self, "container"):
            cw = max(self.container.winfo_width(), 200)
            ch = max(self.container.winfo_height(), 200)
            self._refresh_container_wallpaper(cw, ch)
            self._layout_ui_window(cw, ch)

    def _refresh_root_wallpaper(self, width: int, height: int) -> None:
        if not hasattr(self, "_root_bg"):
            return
        theme = _theme()
        tint = self._bg_tint or theme.screen_bg
        photo = generate_theme_wallpaper(theme, width, height, tint=tint)
        self._root_bg_photo = photo
        self._root_bg.configure(image=photo, bg=tint)
        self._root_bg.lower()

    def _refresh_container_wallpaper(self, width: int, height: int) -> None:
        theme = _theme()
        tint = self._bg_tint or theme.screen_bg
        photo = generate_theme_wallpaper(theme, width, height, tint=tint)
        self._bg_photo = photo
        self.container.delete("wallpaper")
        self.container.create_image(
            0, 0, anchor="nw", image=photo, tags="wallpaper"
        )
        self.container.tag_lower("wallpaper")
        self.container.configure(bg=tint)

    def _layout_ui_window(self, width: int, height: int) -> None:
        if not hasattr(self, "_ui_win"):
            return
        if self._ui_fill:
            pad = 22
            self.container.coords(self._ui_win, pad, pad)
            self.container.itemconfigure(
                self._ui_win,
                anchor="nw",
                width=max(40, width - 2 * pad),
                height=max(40, height - 2 * pad),
            )
        else:
            self._ui.update_idletasks()
            rw = max(self._ui.winfo_reqwidth(), 80)
            rh = max(self._ui.winfo_reqheight(), 80)
            self.container.coords(self._ui_win, width // 2, height // 2)
            self.container.itemconfigure(
                self._ui_win,
                anchor="center",
                width=rw,
                height=rh,
            )
        self.container.tag_raise(self._ui_win)

    def clear(self) -> None:
        self._hide_log_overlay()
        self._hide_target_overlay()
        self._card_faces = []
        self._hand_outer = None
        self.preview = None
        self.preview_status = None
        self.save_btn = None
        self._ui_fill = False
        self._set_screen_bg(_theme().screen_bg)
        for w in self._ui.winfo_children():
            w.destroy()

    def _relayout_ui(self) -> None:
        if not hasattr(self, "container"):
            return
        cw = max(self.container.winfo_width(), 200)
        ch = max(self.container.winfo_height(), 200)
        self._layout_ui_window(cw, ch)

    def _install_widget_wallpaper(self, widget: tk.Misc, tint: str | None = None) -> None:
        """Place a theme-tinted pixel wallpaper behind a widget's children."""
        theme = _theme()
        color = tint or self._bg_tint or theme.screen_bg

        def _paint(_event: tk.Event | None = None) -> None:
            w = max(widget.winfo_width(), 64)
            h = max(widget.winfo_height(), 64)
            if w < 64 or h < 64:
                return
            photo = generate_theme_wallpaper(theme, w, h, tint=color)
            # Keep a per-widget reference so PhotoImage is not GC'd.
            photos = getattr(self, "_widget_bg_photos", {})
            photos[id(widget)] = photo
            self._widget_bg_photos = photos
            existing = getattr(widget, "_pixel_bg_label", None)
            if existing is not None:
                try:
                    existing.configure(image=photo, bg=color)
                    existing.place(x=0, y=0, relwidth=1, relheight=1)
                    existing.lower()
                    return
                except tk.TclError:
                    pass
            label = tk.Label(widget, image=photo, bd=0, highlightthickness=0, bg=color)
            label.place(x=0, y=0, relwidth=1, relheight=1)
            label.lower()
            widget._pixel_bg_label = label  # type: ignore[attr-defined]

        widget.bind("<Configure>", _paint, add="+")
        self.after_idle(_paint)

    def _release_overlay_host(self) -> None:
        if self._target_overlay is None and self._log_overlay is None:
            self._overlay_host.place_forget()

    def _on_escape_overlay(self, _event: tk.Event | None = None) -> str:
        if self._log_overlay is not None:
            self._hide_log_overlay()
            return "break"
        if self._target_overlay is not None:
            self._hide_target_overlay()
            self.pending_card = None
            return "break"
        return "break"

    def _get_bot_photo(self, size: int) -> tk.PhotoImage | None:
        if not BOT_ICON_PATH.exists():
            return None
        size = max(24, size)
        if size in self._bot_photo_cache:
            return self._bot_photo_cache[size]
        if HAS_PIL:
            img = Image.open(BOT_ICON_PATH).convert("RGBA")
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
        else:
            photo = tk.PhotoImage(file=str(BOT_ICON_PATH))
            if photo.width() > size:
                factor = max(1, photo.width() // size)
                photo = photo.subsample(factor, factor)
        self._bot_photo_cache[size] = photo
        return photo

    def _draw_target_dim(self, _event: tk.Event | None = None) -> None:
        if self._target_overlay is None:
            return
        w = self._target_overlay.winfo_width()
        h = self._target_overlay.winfo_height()
        if w < 2 or h < 2:
            return
        self._target_overlay.delete("dim")
        # Dark dim — not solid black; game still faintly visible behind
        self._target_overlay.create_rectangle(
            0,
            0,
            w,
            h,
            fill="#0a0c0b",
            stipple="gray50",
            outline="",
            tags="dim",
        )

    def _hide_target_overlay(self) -> None:
        for child in list(self._overlay_host.winfo_children()):
            if child is self._log_overlay or child is self._log_panel:
                continue
            child.destroy()
        self._target_overlay = None
        self._target_row = None
        self._target_buttons = []
        self._release_overlay_host()

    def _draw_log_dim(self, _event: tk.Event | None = None) -> None:
        """Unused for fullscreen log; kept for resize hook compatibility."""
        return

    def _layout_log_panel(self, _event: tk.Event | None = None) -> None:
        if self._log_panel is None:
            return
        try:
            w = self._log_panel.winfo_width()
            h = self._log_panel.winfo_height()
        except tk.TclError:
            return
        if w < 40 or h < 40:
            return
        theme = _theme()
        fill, accent, _text = theme.cards.normal
        scale = max(2, min(w, h) // 80)
        self._log_panel.delete("frame")
        # Draw frame under content via temporary tag, then lower
        # Use a helper canvas layer: redraw by creating tagged shapes
        items_before = set(self._log_panel.find_all())
        _draw_card_frame(self._log_panel, scale, scale, w - scale, h - scale, fill, accent, scale)
        for item in self._log_panel.find_all():
            if item not in items_before:
                self._log_panel.itemconfigure(item, tags=("frame",))
        self._log_panel.tag_lower("frame")
        if self._log_inner_id is not None:
            inset = 6 * scale
            self._log_panel.coords(self._log_inner_id, w // 2, h // 2)
            self._log_panel.itemconfigure(
                self._log_inner_id,
                width=max(40, w - 2 * inset),
                height=max(40, h - 2 * inset),
            )

    def _hide_log_overlay(self) -> None:
        shells = []
        for w in (self._log_panel, self._log_overlay):
            if w is not None and w not in shells:
                shells.append(w)
        for w in shells:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._log_panel = None
        self._log_overlay = None
        self._log_inner_id = None
        self.log = None
        self._release_overlay_host()

    def _show_log_overlay(self) -> None:
        self._hide_target_overlay()
        self._hide_log_overlay()
        self._raise_overlay_layer()
        theme = _theme()
        fill, accent, _text_color = theme.cards.normal

        # Fullscreen shell — no separate dim layer
        shell = tk.Canvas(
            self._overlay_host,
            highlightthickness=0,
            bd=0,
            bg=theme.log_bg,
        )
        shell.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._log_overlay = shell
        self._log_panel = shell

        inner = tk.Frame(shell, bg=theme.log_bg)
        self._log_inner_id = shell.create_window(0, 0, window=inner, anchor="center")

        header = tk.Frame(inner, bg=theme.log_bg)
        header.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(
            header,
            text="GAME LOG",
            fg=accent,
            bg=theme.log_bg,
            font=(_font_family(), 20, "bold"),
        ).pack(side="left")
        PixelCloseButton(
            header,
            command=self._hide_log_overlay,
            size=LOG_CLOSE_SIZE,
            bg=theme.log_bg,
        ).pack(side="right")

        log_frame = tk.Frame(inner, bg=theme.log_bg)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        scrollbar = tk.Scrollbar(
            log_frame, bg=theme.scale_trough, troughcolor=theme.log_bg
        )
        scrollbar.pack(side="right", fill="y")

        self.log = tk.Text(
            log_frame,
            bg=theme.log_bg,
            fg=theme.log_fg,
            insertbackground=theme.log_fg,
            font=(_font_family(), 12),
            relief="flat",
            wrap="word",
            state="disabled",
            yscrollcommand=scrollbar.set,
            padx=12,
            pady=12,
        )
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log.yview)
        self._render_game_log()

        shell.bind("<Configure>", self._layout_log_panel)
        self.after_idle(self._layout_log_panel)
        self._raise_overlay_layer()

    def _target_subtitle(self, card: Card, target_idx: int) -> str:
        if card.heal_any:
            return "heal target"
        if target_idx == self.active:
            return "heal you"
        return "attack"

    def _layout_target_buttons(self, _event: tk.Event | None = None) -> None:
        if not self._target_buttons or self._target_row is None:
            return
        fw = self._target_row.winfo_width()
        fh = self._target_row.winfo_height()
        if fw < TARGET_MIN or fh < TARGET_MIN:
            return
        n = len(self._target_buttons)
        size, gap = target_size_for_area(fw, fh, n)
        total_w = n * size + gap * max(0, n - 1)
        start_x = max(0, (fw - total_w) // 2)
        y = max(0, (fh - size) // 2)
        for i, btn in enumerate(self._target_buttons):
            btn.set_size(size)
            btn.place(x=start_x + i * (size + gap), y=y, width=size, height=size)

    def _show_target_overlay(self, card: Card) -> None:
        self._hide_log_overlay()
        self._hide_target_overlay()
        self._raise_overlay_layer()
        self._target_overlay = tk.Canvas(
            self._overlay_host,
            highlightthickness=0,
            bd=0,
            bg=_theme().overlay_bg,
        )
        self._target_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._target_overlay.bind("<Configure>", self._draw_target_dim)
        self.after_idle(self._draw_target_dim)

        panel = tk.Frame(
            self._overlay_host,
            bg=_theme().panel_bg,
            highlightbackground=_theme().panel_border,
            highlightthickness=2,
            padx=20,
            pady=16,
        )
        panel.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            panel,
            text=f"Choose target for {card.name}",
            fg=_theme().title_fg,
            bg=_theme().panel_bg,
            font=(_font_family(), 14, "bold"),
        ).pack(pady=(0, 12))

        self._target_row = tk.Frame(panel, bg=_theme().panel_bg, width=560, height=220)
        self._target_row.pack()
        self._target_row.pack_propagate(False)
        self._target_buttons = []

        for i, p in enumerate(self.players):
            if not p.alive:
                continue
            btn = RoundedTargetButton(
                self._target_row,
                p,
                self._target_subtitle(card, i),
                is_self=(i == self.active),
                bot_photo_getter=self._get_bot_photo,
                command=(lambda idx=i: self.confirm_play(idx)),
            )
            self._target_buttons.append(btn)

        self._target_row.bind("<Configure>", self._layout_target_buttons)
        self.after_idle(self._layout_target_buttons)
        self._raise_overlay_layer()

    def _complete_play(self) -> None:
        self.pending_card = None
        self.pending_target_idx = None
        self._busy = True
        self._borrows, return_logs = return_expired_borrows(
            self.players, self.active, self._borrows
        )
        for line in return_logs:
            self.append_log("  " + line)
        for line in tick_turn_cooldowns(self.players, self.active):
            self.append_log("  " + line)
        self.after(TURN_DELAY_MS, self.after_resolve)

    def _layout_hand_cards(self, _event: tk.Event | None = None) -> None:
        if not self._card_faces or self._hand_outer is None:
            return
        fw = self._hand_outer.winfo_width()
        fh = self._hand_outer.winfo_height()
        if fw < CARD_MIN_W or fh < CARD_MIN_W:
            return

        n = len(self._card_faces)
        gap = max(CARD_GAP_MIN, fw // 80)
        card_w, card_h = card_size_for_area(fw, fh, n)
        total_w = n * card_w + gap * max(0, n - 1)
        start_x = max(0, (fw - total_w) // 2)
        y = max(0, (fh - card_h) // 2)

        for i, face in enumerate(self._card_faces):
            face.set_size(card_w, card_h)
            face.place(x=start_x + i * (card_w + gap), y=y, width=card_w, height=card_h)

    def show_setup(self) -> None:
        self._screen = "setup"
        self.clear()
        theme = _theme()
        center = tk.Frame(self._ui, bg=theme.screen_bg)
        center.pack(expand=True)
        self._install_widget_wallpaper(center, theme.screen_bg)

        ttk.Label(center, text="CRASH OUT", style="SetupTitle.TLabel").pack()
        ttk.Label(
            center,
            text=(
                "Window mode — craft cards, then play hotseat or vs bot. "
                "In multiplayer, each player builds a deck; craftable cards are then "
                "shuffled and re-dealt (Mercy and steal stay with their owner)."
            ),
            style="SetupBody.TLabel",
            wraplength=720,
            justify="center",
        ).pack(pady=(12, 28))

        form = tk.Frame(center, bg=theme.screen_bg)
        form.pack()

        self.mode_var = tk.StringVar(value="1")
        ttk.Label(form, text="Match size", style="SetupBody.TLabel").grid(
            row=0, column=0, sticky="e", pady=8, padx=8
        )
        modes = ttk.Combobox(
            form,
            textvariable=self.mode_var,
            values=[
                "1 — vs bot",
                "2 players",
                "3 players",
                "4 players",
            ],
            state="readonly",
            width=18,
            font=(_font_family(), 16),
            style="Setup.TCombobox",
        )
        modes.current(0)
        modes.grid(row=0, column=1, sticky="w", padx=8)

        self.hp_var = tk.StringVar(value=str(DEFAULT_STARTING_HP))
        ttk.Label(form, text="Starting HP", style="SetupBody.TLabel").grid(
            row=1, column=0, sticky="e", pady=8, padx=8
        )
        ttk.Entry(
            form,
            textvariable=self.hp_var,
            width=12,
            font=(_font_family(), 16),
            style="Setup.TEntry",
        ).grid(row=1, column=1, sticky="w", padx=8)

        self.pp_var = tk.StringVar(value=str(DEFAULT_POWER_POINTS))
        ttk.Label(form, text="Power points / card", style="SetupBody.TLabel").grid(
            row=2, column=0, sticky="e", pady=8, padx=8
        )
        ttk.Entry(
            form,
            textvariable=self.pp_var,
            width=12,
            font=(_font_family(), 16),
            style="Setup.TEntry",
        ).grid(row=2, column=1, sticky="w", padx=8)

        self.deck_size_var = tk.IntVar(value=DECK_SIZE)
        ttk.Label(form, text="Max cards / deck", style="SetupBody.TLabel").grid(
            row=3, column=0, sticky="e", pady=8, padx=8
        )
        deck_row = tk.Frame(form, bg=theme.screen_bg)
        deck_row.grid(row=3, column=1, sticky="w", padx=8)
        ttk.Button(
            deck_row,
            text="-",
            style="Setup.TButton",
            width=3,
            command=self._deck_size_down,
        ).pack(side="left")
        self._deck_size_label = ttk.Label(
            deck_row,
            textvariable=self.deck_size_var,
            style="SetupBody.TLabel",
            width=4,
            anchor="center",
        )
        self._deck_size_label.pack(side="left", padx=8)
        ttk.Button(
            deck_row,
            text="+",
            style="Setup.TButton",
            width=3,
            command=self._deck_size_up,
        ).pack(side="left")

        self._setup_rules_label = ttk.Label(
            center,
            text=self._setup_rules_text(DECK_SIZE),
            style="SetupBody.TLabel",
            justify="center",
            wraplength=720,
        )
        self._setup_rules_label.pack(pady=(24, 12))

        ttk.Button(
            center,
            text="Continue to Card Lab",
            style="Setup.TButton",
            command=self.begin_card_lab,
        ).pack(pady=8)

        theme_row = tk.Frame(center, bg=theme.screen_bg)
        theme_row.pack(pady=(16, 4))
        ttk.Button(
            theme_row,
            text="Creative Theme",
            style="Setup.TButton",
            command=self._on_random_theme,
        ).pack(side="left", padx=6)
        ttk.Button(
            theme_row,
            text="Default Theme",
            style="Setup.TButton",
            command=self._on_reset_theme,
        ).pack(side="left", padx=6)
        self._theme_label = ttk.Label(
            center,
            text=f"Theme: {theme.name} ({theme.card_style}) — {theme.font_family}",
            style="SetupBody.TLabel",
        )
        self._theme_label.pack(pady=(8, 0))
        self.after_idle(self._relayout_ui)

    def _setup_rules_text(self, deck_size: int) -> str:
        last = deck_size
        lines = [
            f"Max HP = 2x starting. Last card ({last}) = Mercy "
            f"({FIFTH_CARD_HEAL} heal any target).",
            f"Deck size {DECK_SIZE_MIN}-{DECK_SIZE_MAX}.",
        ]
        if allows_duplicate_archetypes(deck_size):
            lines.append(
                f"Above {ARCHETYPE_UNIQUE_LIMIT} cards: duplicate types allowed "
                "(Steal / Heavy Hit still one each)."
            )
        else:
            lines.append(
                f"At {ARCHETYPE_UNIQUE_LIMIT} or fewer cards: each type is unique "
                f"(duplicates unlock above {ARCHETYPE_UNIQUE_LIMIT})."
            )
        return "\n".join(lines)

    def _refresh_setup_rules(self) -> None:
        if getattr(self, "_setup_rules_label", None) is None:
            return
        try:
            if not self._setup_rules_label.winfo_exists():
                return
        except tk.TclError:
            return
        self._setup_rules_label.configure(
            text=self._setup_rules_text(int(self.deck_size_var.get()))
        )

    def _deck_size_up(self) -> None:
        value = clamp_deck_size(int(self.deck_size_var.get()) + 1)
        self.deck_size_var.set(value)
        self._refresh_setup_rules()

    def _deck_size_down(self) -> None:
        value = clamp_deck_size(int(self.deck_size_var.get()) - 1)
        self.deck_size_var.set(value)
        self._refresh_setup_rules()

    def begin_card_lab(self) -> None:
        try:
            hp = int(self.hp_var.get().strip())
            pp = int(self.pp_var.get().strip())
            deck_size = int(self.deck_size_var.get())
        except ValueError:
            messagebox.showerror(
                "Invalid input", "HP, power points, and max cards must be numbers."
            )
            return
        if not (HP_MIN <= hp <= HP_MAX):
            messagebox.showerror("Invalid HP", f"Starting HP must be {HP_MIN}-{HP_MAX}.")
            return
        if not (PP_MIN <= pp <= PP_MAX):
            messagebox.showerror(
                "Invalid PP", f"Power points must be {PP_MIN}-{PP_MAX}."
            )
            return
        if not (DECK_SIZE_MIN <= deck_size <= DECK_SIZE_MAX):
            messagebox.showerror(
                "Invalid deck size",
                f"Max cards must be {DECK_SIZE_MIN}-{DECK_SIZE_MAX}.",
            )
            return

        mode = self.mode_var.get()
        count = int(mode[0])
        self.settings = MatchSettings(count, hp, pp, deck_size)
        self.starting_hp = hp
        self.crafted = []
        self.all_player_decks = []
        self.crafting_player = 1
        self.craft_slot = 1
        self.show_craft()

    def show_craft(self) -> None:
        self._screen = "craft"
        assert self.settings is not None
        self.clear()
        deck_size = self.settings.deck_size
        if self.craft_slot >= deck_size:
            self.crafted.append(make_mercy_card(deck_size, self.crafted))
            if self.settings.vs_bot:
                self.start_match()
            else:
                self._finish_player_craft()
            return

        pp = self.settings.power_points
        if self.settings.vs_bot:
            lab_title = f"Card Lab — Card {self.craft_slot}/{deck_size}"
            lab_hint = (
                f"Spend exactly {pp} power points (damage + heal)."
            )
        else:
            lab_title = (
                f"Card Lab — player-{self.crafting_player} "
                f"— Card {self.craft_slot}/{deck_size}"
            )
            lab_hint = (
                f"player-{self.crafting_player}, spend exactly {pp} power points "
                f"(damage + heal). Craftable cards are shuffled and re-dealt when "
                f"everyone is done. Mercy and steal stay with their owner."
            )
        lab = tk.Frame(self._ui, bg=_theme().screen_bg)
        lab.pack(expand=True)
        self._install_widget_wallpaper(lab, _theme().screen_bg)
        ttk.Label(
            lab,
            text=lab_title,
            style="SetupTitle.TLabel",
        ).pack()
        ThemedArtButton(
            lab,
            "Reset Game",
            command=self._reset_game,
            width=180,
            height=44,
            palette="heavy_hit",
        ).pack(pady=(8, 4))
        steal_hint = (
            f" Optional: one steal card per deck ({STEAL_PP_COST} PP), "
            "or one Heavy Hit (+50% power, 2-turn cooldown, clears target cooldowns 2 turns)."
            if (can_craft_steal(pp) or can_add_heavy_hit_card(self.crafted))
            and not self.settings.vs_bot
            else (
                " Optional: one Heavy Hit per deck (+50% power, 2-turn cooldown, clears target cooldowns 2 turns)."
                if can_add_heavy_hit_card(self.crafted)
                else ""
            )
        )
        type_hint = (
            f"Duplicate types allowed (deck above {ARCHETYPE_UNIQUE_LIMIT}); "
            "Steal / Heavy Hit still one each."
            if self.settings.allow_duplicate_archetypes
            else "No duplicate types (Sanctuary / Caretaker / Allrounder / Bruiser / Wrecker)."
        )
        ttk.Label(
            lab,
            text=f"{lab_hint}{steal_hint} {type_hint}",
            style="SetupBody.TLabel",
            wraplength=800,
            justify="center",
        ).pack(pady=(8, 16))

        self.steal_var = tk.BooleanVar(value=False)
        self.heavy_hit_var = tk.BooleanVar(value=False)
        if can_add_steal_card(self.crafted, pp) and not self.settings.vs_bot:
            ttk.Checkbutton(
                lab,
                text=(
                    f"Steal ability ({STEAL_PP_COST} PP) — "
                    "steal 1 opponent card for 1 turn (one per deck)"
                ),
                variable=self.steal_var,
                command=self._on_steal_toggle,
                style="Lab.TCheckbutton",
            ).pack(pady=(0, 4))
        elif deck_has_steal(self.crafted):
            ttk.Label(
                lab,
                text="Steal already used in this deck (one per deck).",
                style="SetupBody.TLabel",
            ).pack(pady=(0, 4))

        if can_add_heavy_hit_card(self.crafted):
            ttk.Checkbutton(
                lab,
                text=(
                    "Heavy Hit — +50% damage/heal, 2-turn cooldown, clears target "
                    "cooldowns for 2 turns (one per deck)"
                ),
                variable=self.heavy_hit_var,
                command=self._on_heavy_hit_toggle,
                style="Lab.TCheckbutton",
            ).pack(pady=(0, 8))
        elif deck_has_heavy_hit(self.crafted):
            ttk.Label(
                lab,
                text="Heavy Hit already used in this deck (one per deck).",
                style="SetupBody.TLabel",
            ).pack(pady=(0, 8))

        budget = stat_budget(pp, self.steal_var.get())
        self.damage_var = tk.IntVar(value=budget // 2 if budget else 0)
        row = tk.Frame(lab, bg=_theme().screen_bg)
        row.pack(pady=8)
        ttk.Label(row, text="Damage points", style="SetupBody.TLabel").pack(side="left")
        self._craft_scale = ttk.Scale(
            row,
            from_=0,
            to=max(0, budget),
            orient="horizontal",
            length=480,
            style="Green.Horizontal.TScale",
            command=self._on_damage_slide,
        )
        self._craft_scale.pack(side="left", padx=12)

        preview_row = tk.Frame(lab, bg=_theme().screen_bg)
        preview_row.pack(pady=12)
        placeholder = Card(self.craft_slot, "Allrounder", 0, 0)
        self.preview = RoundedCardButton(
            preview_row,
            placeholder,
            width=PREVIEW_CARD_W,
        )
        self.preview.pack()
        self.preview_status = ttk.Label(lab, text="", style="SetupBody.TLabel")
        self.preview_status.pack(pady=(8, 0))

        self.save_btn = ttk.Button(
            lab,
            text="Save card",
            style="Setup.TButton",
            command=self.save_crafted_card,
        )
        self.save_btn.pack(pady=12)
        if budget:
            self._craft_scale.set(budget // 2)
        else:
            self._on_damage_slide("0")

        if self.crafted:
            ttk.Label(lab, text="Deck so far:", style="SetupBody.TLabel").pack(
                pady=(8, 4)
            )
            deck_row = tk.Frame(lab, bg=_theme().screen_bg)
            deck_row.pack()
            for c in self.crafted:
                face = RoundedCardButton(deck_row, c, width=DECK_MINI_W)
                face.pack(side="left", padx=6, pady=4)
        self.after_idle(self._relayout_ui)

    def _craft_budget(self) -> int:
        assert self.settings is not None
        return stat_budget(self.settings.power_points, self.steal_var.get())

    def _on_steal_toggle(self) -> None:
        if self.steal_var.get():
            self.heavy_hit_var.set(False)
        self._refresh_craft_slider()

    def _on_heavy_hit_toggle(self) -> None:
        if self.heavy_hit_var.get():
            self.steal_var.set(False)
        self._refresh_craft_slider()

    def _refresh_craft_slider(self) -> None:
        if self._craft_scale is None:
            return
        budget = self._craft_budget()
        self._craft_scale.configure(to=max(0, budget))
        damage = min(self.damage_var.get(), budget)
        self.damage_var.set(damage)
        if budget:
            self._craft_scale.set(damage)
        self._on_damage_slide(str(damage))

    def _on_damage_slide(self, value: str) -> None:
        assert self.settings is not None
        preview_ok = self.preview is not None and self.preview.winfo_exists()
        status_ok = (
            self.preview_status is not None and self.preview_status.winfo_exists()
        )
        save_ok = self.save_btn is not None and self.save_btn.winfo_exists()
        if not preview_ok or not status_ok or not save_ok:
            return
        budget = self._craft_budget()
        damage = int(float(value))
        damage = max(0, min(budget, damage))
        heal = budget - damage
        self.damage_var.set(damage)
        archetype = name_for_split(damage, heal, budget if budget else 1)
        heavy_hit = self.heavy_hit_var.get()
        steals = self.steal_var.get()
        name = "Heavy Hit" if heavy_hit else archetype
        card = Card(
            id=self.craft_slot,
            name=name,
            damage=damage,
            heal=heal,
            steals=steals,
            heavy_hit=heavy_hit,
        )
        taken = archetype_taken(name, self.crafted)
        block_dupe = taken and not self.settings.allow_duplicate_archetypes
        if heavy_hit and deck_has_heavy_hit(self.crafted):
            block_dupe = True
        if steals and deck_has_steal(self.crafted):
            block_dupe = True
        self.preview.set_card(card, disabled=block_dupe)
        if block_dupe:
            if heavy_hit and deck_has_heavy_hit(self.crafted):
                msg = "Heavy Hit already in deck (attribute — one only)."
            elif steals and deck_has_steal(self.crafted):
                msg = "Steal already in deck (attribute — one only)."
            else:
                msg = "Already in deck — pick another split."
            self.preview_status.configure(text=msg)
            self.save_btn.state(["disabled"])
        else:
            if taken and self.settings.allow_duplicate_archetypes:
                self.preview_status.configure(
                    text="Duplicate type allowed (deck above 7)."
                )
            else:
                self.preview_status.configure(text="")
            self.save_btn.state(["!disabled"])

    def save_crafted_card(self) -> None:
        assert self.settings is not None
        damage = self.damage_var.get()
        steals = self.steal_var.get()
        heavy_hit = self.heavy_hit_var.get()
        try:
            card = craft_card(
                self.craft_slot,
                damage,
                self.settings.power_points,
                self.crafted,
                steals=steals,
                heavy_hit=heavy_hit,
                deck_size=self.settings.deck_size,
            )
        except ValueError as exc:
            messagebox.showwarning("Invalid card", str(exc))
            return
        self.crafted.append(card)
        self.craft_slot += 1
        self._craft_scale = None
        self.show_craft()

    def _finish_player_craft(self) -> None:
        assert self.settings is not None
        self.all_player_decks.append(list(self.crafted))
        self.crafted = []
        self.craft_slot = 1
        if self.crafting_player < self.settings.player_count:
            self.crafting_player += 1
            self.show_craft()
        else:
            self.start_match()

    def start_match(self) -> None:
        assert self.settings is not None
        if self.settings.vs_bot:
            bot_deck = make_bot_deck(
                self.settings.power_points, self.settings.deck_size
            )
            self.players = make_solo_players(
                self.crafted, bot_deck, self.settings.starting_hp
            )
            start_msg = f"Match started. {self.players[0].name}'s turn."
        else:
            self.players = make_players_from_mixed_decks(
                self.all_player_decks, self.settings.starting_hp
            )
            start_msg = (
                "Craftable cards shuffled and dealt! "
                f"{self.players[0].name}'s turn."
            )
        self.active = 0
        self.pending_card = None
        self.pending_target_idx = None
        self._borrows = []
        self._game_log = []
        self.show_play(start_msg)

    def _log_turn_banner(self, banner_msg: str) -> None:
        if not banner_msg:
            return
        entry = f"--- {banner_msg} ---"
        if not self._game_log or self._game_log[-1] != entry:
            self.append_log(entry)

    def _render_game_log(self) -> None:
        if self.log is None:
            return
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        for line in self._game_log:
            self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def show_play(self, banner_msg: str = "") -> None:
        self._screen = "play"
        self._play_banner = banner_msg
        self.clear()
        self._busy = False
        self.log = None
        player = self.players[self.active]
        if not self._game_log:
            self._game_log.append("Play a card, then choose a target.")
        self._log_turn_banner(banner_msg or f"Turn — {player.name}")

        self._ui_fill = True
        self.after_idle(self._relayout_ui)
        theme = _theme()
        tint = self._bg_tint or theme.screen_bg

        # Pixel-art panel under the play UI (shows in gaps / as base texture).
        self._ui.update_idletasks()
        self._install_widget_wallpaper(self._ui, tint)

        hud_outer = tk.Frame(self._ui, bg=tint)
        hud_outer.pack(fill="x", pady=(0, 10))
        health_bar = tk.Frame(hud_outer, bg=tint)
        health_bar.pack(anchor="center")
        for i, p in enumerate(self.players):
            chip = PixelHudChip(health_bar, p, is_active=(i == self.active))
            chip.pack(side="left", padx=6)

        play_area = tk.Frame(self._ui, bg=tint)
        play_area.pack(fill="both", expand=True)
        self._install_widget_wallpaper(play_area, tint)

        ttk.Label(play_area, text="CRASH OUT", style="Title.TLabel").pack()
        ttk.Label(
            play_area,
            text=banner_msg or f"Turn — {player.name}",
            style="Body.TLabel",
        ).pack(pady=(4, 6))

        btn_row = tk.Frame(play_area, bg=_theme().screen_bg)
        btn_row.pack(pady=(0, 10))
        ThemedArtButton(
            btn_row,
            "Log",
            command=self._show_log_overlay,
            width=140,
            height=44,
            palette="selected",
        ).pack(side="left", padx=6)
        ThemedArtButton(
            btn_row,
            "Reset Game",
            command=self._reset_game,
            width=180,
            height=44,
            palette="heavy_hit",
        ).pack(side="left", padx=6)

        action = tk.Frame(play_area, bg=_theme().screen_bg)
        action.pack(fill="both", expand=True)

        if not player.alive:
            self.after(TURN_DELAY_MS, self.advance_turn)
            return

        if player.is_bot:
            ttk.Label(
                action, text="Bot is thinking...", style="Body.TLabel"
            ).pack()
            self.after(TURN_DELAY_MS, self.run_bot_turn)
            return

        ttk.Label(action, text="Your hand", style="Body.TLabel").pack()
        self._hand_outer = tk.Frame(action, bg=_theme().screen_bg)
        self._hand_outer.pack(fill="both", expand=True, pady=8)
        self._card_faces = []
        for card in player.hand:
            cooling = card_is_cooling(player, card)
            face = RoundedCardButton(
                self._hand_outer,
                card,
                disabled=cooling,
                command=(None if cooling else (lambda c=card: self.pick_card(c))),
            )
            self._card_faces.append(face)
        self._hand_outer.bind("<Configure>", self._layout_hand_cards)
        self.after_idle(self._layout_hand_cards)

    def append_log(self, text: str) -> None:
        self._game_log.append(text)
        if self.log is None:
            return
        try:
            self.log.configure(state="normal")
            self.log.insert("end", text + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        except tk.TclError:
            pass

    def pick_card(self, card: Card) -> None:
        if self._busy:
            return
        player = self.players[self.active]
        if card_is_cooling(player, card):
            return
        self.pending_card = card
        self._show_target_overlay(card)

    def confirm_play(self, target_idx: int) -> None:
        if self._busy or self.pending_card is None:
            return
        self._hide_target_overlay()
        card = self.pending_card
        player = self.players[self.active]
        mark_card_played(player, card)
        self.append_log(f"{player.name} plays {card.name}")
        self.append_log(
            f"Target: {describe_target(card, self.players, self.active, target_idx)}"
        )
        for line in resolve_card(card, self.players, self.active, target_idx):
            self.append_log("  " + line)
        for line in resolve_steal(
            card, self.players, self.active, target_idx, self._borrows
        ):
            self.append_log("  " + line)
        self._complete_play()

    def run_bot_turn(self) -> None:
        player = self.players[self.active]
        choice = bot_choose_play(self.players, self.active, self.starting_hp)
        if choice is None:
            player.last_card_id = None
            self.append_log("Bot has no playable cards — skipped.")
            self._borrows, return_logs = return_expired_borrows(
                self.players, self.active, self._borrows
            )
            for line in return_logs:
                self.append_log("  " + line)
            for line in tick_turn_cooldowns(self.players, self.active):
                self.append_log("  " + line)
            self.after(TURN_DELAY_MS, self.after_resolve)
            return
        card, target_idx, reason = choice
        mark_card_played(player, card)
        self.append_log(f"Bot plan: {reason}")
        self.append_log(f"Bot plays {card.name}")
        self.append_log(
            f"Target: {describe_target(card, self.players, self.active, target_idx)}"
        )
        for line in resolve_card(card, self.players, self.active, target_idx):
            self.append_log("  " + line)
        self._borrows, return_logs = return_expired_borrows(
            self.players, self.active, self._borrows
        )
        for line in return_logs:
            self.append_log("  " + line)
        for line in tick_turn_cooldowns(self.players, self.active):
            self.append_log("  " + line)
        self.after(TURN_DELAY_MS, self.after_resolve)

    def after_resolve(self) -> None:
        winner = check_winner(self.players)
        if winner is not None:
            self.show_game_over(winner.name)
            return
        self.advance_turn()

    def advance_turn(self) -> None:
        nxt = next_alive_index(self.players, self.active)
        if nxt is None:
            self.show_game_over(None)
            return
        self.active = nxt
        self.show_play(f"Turn — {self.players[self.active].name}")

    def show_game_over(self, winner: str | None) -> None:
        self._screen = "game_over"
        self._game_over_winner = winner
        self.clear()
        theme = _theme()
        vs_bot = self.settings is not None and self.settings.vs_bot
        human_won = vs_bot and winner is not None and winner != BOT_NAME
        if vs_bot:
            bg = theme.win_bg if human_won else theme.lose_bg
            fg = "#e8f8ee" if human_won else "#ffe8e0"
        else:
            bg = theme.screen_bg
            fg = theme.title_fg
        self._set_screen_bg(bg)
        center = tk.Frame(self._ui, bg=bg)
        center.pack(expand=True)
        self._install_widget_wallpaper(center, bg)
        title = "-=You Win=-" if human_won else "-=Game Over=-"
        tk.Label(
            center,
            text=title,
            bg=bg,
            fg=fg,
            font=(_font_family(), 64),
        ).pack(pady=(0, 20))
        if not human_won:
            msg = f"{winner} wins!" if winner else "No one left standing."
            tk.Label(
                center,
                text=msg,
                bg=bg,
                fg=fg,
                font=(_font_family(), 24),
                justify="center",
            ).pack(pady=20)
        for p in self.players:
            status = "OUT" if not p.alive else f"{p.hp}/{p.max_hp} HP"
            tk.Label(
                center,
                text=f"{p.name}: {status}",
                bg=bg,
                fg=fg,
                font=(_font_family(), 24),
            ).pack(pady=4)
        btn_row = tk.Frame(center, bg=bg)
        btn_row.pack(pady=(24, 0))
        ThemedArtButton(
            btn_row,
            "Reset Game",
            command=self._reset_game,
            width=200,
            height=52,
            palette="heavy_hit",
            bg=bg,
        ).pack(side="left", padx=8)
        ThemedArtButton(
            btn_row,
            "Quit",
            command=self.destroy,
            width=140,
            height=52,
            palette="normal",
            bg=bg,
        ).pack(side="left", padx=8)
        self.after_idle(self._relayout_ui)


def main() -> None:
    app = CrashOutApp()
    app.mainloop()


if __name__ == "__main__":
    main()
