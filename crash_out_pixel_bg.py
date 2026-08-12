#!/usr/bin/env python3
"""Procedural pixel-art wallpapers tinted to the active theme."""

from __future__ import annotations

import random
import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crash_out_themes import GameTheme

try:
    from PIL import Image, ImageTk

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    raw = color.lstrip("#")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def _shift_rgb(rgb: tuple[int, int, int], delta: int) -> tuple[int, int, int]:
    return tuple(max(0, min(255, c + delta)) for c in rgb)  # type: ignore[return-value]


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))  # type: ignore[return-value]


def _palette(theme: GameTheme, tint: str | None = None) -> list[tuple[int, int, int]]:
    base = _hex_to_rgb(tint or theme.screen_bg)
    accent = _hex_to_rgb(theme.cards.normal[1])
    title = _hex_to_rgb(theme.title_fg)
    panel = _hex_to_rgb(theme.panel_bg)
    return [
        base,
        _shift_rgb(base, 18),
        _shift_rgb(base, -14),
        _mix(base, accent, 0.22),
        _mix(base, accent, 0.38),
        _mix(base, title, 0.12),
        _mix(base, panel, 0.35),
        _shift_rgb(_mix(base, accent, 0.5), -20),
    ]


def _cell_size(style: str) -> int:
    return {
        "neon": 10,
        "lava": 12,
        "ice": 10,
        "arcade": 8,
        "gold": 12,
        "circuit": 10,
        "stone": 14,
        "shadow": 12,
        "pixel": 12,
    }.get(style, 12)


def _paint_pixel_grid(
    theme: GameTheme,
    cols: int,
    rows: int,
    tint: str | None = None,
) -> list[list[tuple[int, int, int]]]:
    rng = random.Random(f"{theme.name}:{theme.card_style}:{tint or theme.screen_bg}:{cols}x{rows}")
    colors = _palette(theme, tint)
    base = colors[0]
    style = theme.card_style
    grid = [[base for _ in range(cols)] for _ in range(rows)]

    def set_px(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < cols and 0 <= y < rows:
            grid[y][x] = color

    if style == "neon":
        for y in range(rows):
            for x in range(cols):
                grid[y][x] = colors[1] if (x + y) % 7 == 0 else colors[2 if (x * 3 + y) % 11 == 0 else 0]
        for x in range(0, cols, 6):
            for y in range(rows):
                set_px(x, y, colors[4])
        for y in range(0, rows, 6):
            for x in range(cols):
                set_px(x, y, colors[3])
        for _ in range(max(8, cols * rows // 40)):
            set_px(rng.randrange(cols), rng.randrange(rows), colors[5])

    elif style == "lava":
        for y in range(rows):
            for x in range(cols):
                n = (x * 5 + y * 3 + rng.randrange(3)) % 9
                grid[y][x] = colors[0 if n > 5 else (4 if n > 2 else 7)]
        for _ in range(cols):
            x, y = rng.randrange(cols), rng.randrange(rows)
            for i in range(rng.randint(3, 8)):
                set_px(x, y, colors[4])
                x += rng.choice((-1, 0, 1))
                y += rng.choice((-1, 0, 1))

    elif style == "ice":
        for y in range(rows):
            for x in range(cols):
                band = (x + y) % 8
                grid[y][x] = colors[1 if band < 2 else (5 if band == 4 else 0)]
        for _ in range(max(12, cols // 2)):
            x = rng.randrange(cols)
            for y in range(rows):
                if rng.random() < 0.55:
                    set_px(x, y, colors[5])
                    set_px(x + 1, y, colors[1])

    elif style == "arcade":
        for y in range(rows):
            stripe = colors[3 if (y // 2) % 2 == 0 else 0]
            for x in range(cols):
                grid[y][x] = colors[4] if (x + y) % 5 == 0 else stripe
        for y in range(0, rows, 4):
            for x in range(0, cols, 4):
                set_px(x, y, colors[5])

    elif style == "gold":
        for y in range(rows):
            for x in range(cols):
                grid[y][x] = colors[(x // 3 + y // 3) % 3]
        for y in range(2, rows - 2):
            for x in range(2, cols - 2):
                if x in (2, cols - 3) or y in (2, rows - 3):
                    set_px(x, y, colors[4])
        for _ in range(max(6, cols // 3)):
            set_px(rng.randrange(cols), rng.randrange(rows), colors[5])

    elif style == "circuit":
        for y in range(rows):
            for x in range(cols):
                grid[y][x] = colors[2 if (x % 4 == 0 or y % 4 == 0) else 0]
        for y in range(1, rows, 4):
            for x in range(1, cols, 4):
                set_px(x, y, colors[4])
                if rng.random() < 0.5:
                    set_px(x + 1, y, colors[3])
                if rng.random() < 0.5:
                    set_px(x, y + 1, colors[3])

    elif style == "stone":
        brick_w, brick_h = 4, 2
        for y in range(rows):
            row = y // brick_h
            offset = (brick_w // 2) if row % 2 else 0
            for x in range(cols):
                tone = colors[1 if ((x + offset) // brick_w + row) % 2 == 0 else 2]
                if x % brick_w == offset % brick_w or y % brick_h == 0:
                    tone = colors[7]
                grid[y][x] = tone

    elif style == "shadow":
        for y in range(rows):
            for x in range(cols):
                grid[y][x] = colors[2 if (x * y + x) % 13 == 0 else 0]
        for y in range(rows):
            for x in range(cols):
                if abs((x - cols // 2) * (y - rows // 2)) % 17 == 0:
                    set_px(x, y, colors[3])

    else:  # pixel / default — chunky dithered noise
        for y in range(rows):
            for x in range(cols):
                n = rng.randrange(100)
                if n < 8:
                    grid[y][x] = colors[4]
                elif n < 20:
                    grid[y][x] = colors[1]
                elif n < 35:
                    grid[y][x] = colors[2]
                else:
                    grid[y][x] = colors[0]
        # sparse accent clusters
        for _ in range(max(4, cols * rows // 80)):
            cx, cy = rng.randrange(cols), rng.randrange(rows)
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if rng.random() < 0.6:
                        set_px(cx + dx, cy + dy, colors[3])

    return grid


def _photo_from_grid_pil(
    grid: list[list[tuple[int, int, int]]],
    cell: int,
    width: int,
    height: int,
) -> tk.PhotoImage:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    img = Image.new("RGB", (cols, rows))
    pixels = img.load()
    assert pixels is not None
    for y in range(rows):
        for x in range(cols):
            pixels[x, y] = grid[y][x]
    img = img.resize((cols * cell, rows * cell), Image.Resampling.NEAREST)
    if img.size != (width, height):
        # Crop or pad to exact window size while keeping pixel edges crisp.
        canvas = Image.new("RGB", (width, height), grid[0][0] if rows and cols else (0, 0, 0))
        canvas.paste(img, (0, 0))
        img = canvas.crop((0, 0, width, height))
    return ImageTk.PhotoImage(img)


def _photo_from_grid_tk(
    grid: list[list[tuple[int, int, int]]],
    cell: int,
    width: int,
    height: int,
) -> tk.PhotoImage:
    """Fallback without PIL — build a small image and zoom it."""
    rows = len(grid)
    cols = len(grid[0]) if rows else 1
    photo = tk.PhotoImage(width=cols, height=rows)
    # put() accepts row-wise color data
    for y in range(rows):
        row = " ".join(_rgb_to_hex(*grid[y][x]) for x in range(cols))
        photo.put("{" + row + "}", to=(0, y))
    zoomed = photo.zoom(max(1, cell), max(1, cell))
    # If zoomed is larger than needed, leave it — Label will clip.
    # If smaller, the Label centers/stretches poorly; pad by creating full size.
    if zoomed.width() < width or zoomed.height() < height:
        full = tk.PhotoImage(width=width, height=height)
        full.paste(zoomed)
        return full
    return zoomed


def generate_theme_wallpaper(
    theme: GameTheme,
    width: int,
    height: int,
    *,
    tint: str | None = None,
) -> tk.PhotoImage:
    """
    Build a pixel-art wallpaper matching the theme tint and card_style.
    `tint` overrides the base color (e.g. win/lose screens).
    """
    width = max(64, int(width))
    height = max(64, int(height))
    cell = _cell_size(theme.card_style)
    cols = max(8, (width + cell - 1) // cell)
    rows = max(8, (height + cell - 1) // cell)
    grid = _paint_pixel_grid(theme, cols, rows, tint=tint)
    if HAS_PIL:
        return _photo_from_grid_pil(grid, cell, width, height)
    return _photo_from_grid_tk(grid, cell, width, height)
