#!/usr/bin/env python3
"""Theme presets and random theme generation for the window UI."""

from __future__ import annotations

import ctypes
import random
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

CardStyle = Literal[
    "pixel", "neon", "stone", "ice", "lava", "arcade", "gold", "circuit", "shadow"
]

CARD_STYLES: tuple[CardStyle, ...] = (
    "pixel", "neon", "stone", "ice", "lava", "arcade", "gold", "circuit", "shadow",
)

FR_PRIVATE = 0x10
HWND_BROADCAST = 0xFFFF
WM_FONTCHANGE = 0x001D

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FONT_PATH = (
    PROJECT_ROOT / "Minecraft-20230518T220806Z-001 (1)" / "Minecraft" / "arial.ttf"
)
FONT_DIR = PROJECT_ROOT / "Minecraft-20230518T220806Z-001 (1)" / "Minecraft"


@dataclass(frozen=True)
class CardArt:
    """Pixel-card fill / accent / text colors."""

    normal: tuple[str, str, str]
    heal: tuple[str, str, str]
    heavy_hit: tuple[str, str, str]
    steal: tuple[str, str, str]
    disabled: tuple[str, str, str]
    selected: tuple[str, str, str]


@dataclass(frozen=True)
class GameTheme:
    name: str
    font_path: Path | None
    font_family: str
    screen_bg: str
    win_bg: str
    lose_bg: str
    title_fg: str
    body_fg: str
    log_bg: str
    log_fg: str
    overlay_bg: str
    panel_bg: str
    panel_border: str
    target_bg: str
    hud_active: tuple[str, str, str]
    hud_idle: tuple[str, str, str]
    hud_dead: tuple[str, str, str]
    target_self: tuple[str, str, str]
    target_other: tuple[str, str, str]
    scale_trough: str
    scale_fill: str
    scale_border: str
    scale_light: str
    scale_dark: str
    cards: CardArt = field(repr=False)
    card_style: CardStyle = "pixel"


def _register_font_file(font_path: Path) -> None:
    if not font_path.exists() or not hasattr(ctypes, "windll"):
        return
    add_ex = getattr(ctypes.windll.gdi32, "AddFontResourceExW", None)
    if add_ex is None:
        return
    try:
        add_ex(str(font_path), FR_PRIVATE, None)
        ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0)
    except Exception:
        pass


def _read_font_family(font_path: Path) -> str:
    """Best-effort TTF/OTF family name (no external deps)."""
    try:
        data = font_path.read_bytes()
        if len(data) < 12:
            return font_path.stem
        num_tables = struct.unpack(">H", data[4:6])[0]
        name_offset = None
        off = 12
        for _ in range(num_tables):
            tag, _csum, start, length = struct.unpack(">4sIII", data[off : off + 16])
            off += 16
            if tag == b"name":
                name_offset = start
                break
        if name_offset is None:
            return font_path.stem
        count, string_offset = struct.unpack(">HH", data[name_offset + 2 : name_offset + 6])
        for i in range(count):
            rec = name_offset + 6 + i * 12
            plat, enc, lang, name_id, slen, soff = struct.unpack(
                ">HHHHHH", data[rec : rec + 12]
            )
            if name_id != 1:
                continue
            raw = data[name_offset + string_offset + soff : name_offset + string_offset + soff + slen]
            if plat == 3:
                return raw.decode("utf-16-be", errors="replace").strip() or font_path.stem
            if plat == 1:
                return raw.decode("latin-1", errors="replace").strip() or font_path.stem
    except Exception:
        pass
    return font_path.stem


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    h, s, l = h % 1.0, _clamp(s), _clamp(l)
    if s == 0:
        val = int(l * 255)
        return f"#{val:02x}{val:02x}{val:02x}"

    def hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = int(hue_to_rgb(p, q, h + 1 / 3) * 255)
    g = int(hue_to_rgb(p, q, h) * 255)
    b = int(hue_to_rgb(p, q, h - 1 / 3) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"


def _shift_hex(color: str, delta: int) -> str:
    raw = color.lstrip("#")
    rgb = [max(0, min(255, int(raw[i : i + 2], 16) + delta)) for i in (0, 2, 4)]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _card_triplet(h: float, s: float, l_fill: float, l_accent: float, l_text: float) -> tuple[str, str, str]:
    return (
        _hsl_to_hex(h, s, l_fill),
        _hsl_to_hex(h, min(1.0, s + 0.15), l_accent),
        _hsl_to_hex(h, max(0.0, s - 0.2), l_text),
    )


def _build_theme(
    *,
    name: str,
    font_path: Path | None,
    font_family: str,
    screen_bg: str,
    win_bg: str,
    lose_bg: str,
    title_fg: str,
    body_fg: str,
    log_bg: str,
    log_fg: str,
    overlay_bg: str,
    panel_bg: str,
    panel_border: str,
    target_bg: str,
    cards: CardArt,
    scale_hue: float,
    hud_active: tuple[str, str, str] | None = None,
    hud_idle: tuple[str, str, str] | None = None,
    hud_dead: tuple[str, str, str] | None = None,
    target_self: tuple[str, str, str] | None = None,
    target_other: tuple[str, str, str] | None = None,
    card_style: CardStyle = "pixel",
) -> GameTheme:
    return GameTheme(
        name=name,
        font_path=font_path,
        font_family=font_family,
        screen_bg=screen_bg,
        win_bg=win_bg,
        lose_bg=lose_bg,
        title_fg=title_fg,
        body_fg=body_fg,
        log_bg=log_bg,
        log_fg=log_fg,
        overlay_bg=overlay_bg,
        panel_bg=panel_bg,
        panel_border=panel_border,
        target_bg=target_bg,
        hud_active=hud_active or ("#3d5a45", "#f0c674", "#fff6d8"),
        hud_idle=hud_idle or (_shift_hex(screen_bg, 18), "#8a948c", "#c4b59a"),
        hud_dead=hud_dead or cards.disabled,
        target_self=target_self or ("#3d5a45", "#f0c674", "#f7f0e0"),
        target_other=target_other or (_shift_hex(screen_bg, 12), "#c4b59a", "#f2e9d8"),
        scale_trough=_hsl_to_hex(scale_hue, 0.25, 0.18),
        scale_fill=_hsl_to_hex(scale_hue, 0.45, 0.55),
        scale_border=_hsl_to_hex(scale_hue, 0.35, 0.42),
        scale_light=_hsl_to_hex(scale_hue, 0.45, 0.65),
        scale_dark=_hsl_to_hex(scale_hue, 0.35, 0.32),
        card_style=card_style,
        cards=cards,
    )


def _theme_font(filename: str, fallback: str = "Minecraft") -> tuple[Path | None, str]:
    path = FONT_DIR / filename
    if path.exists():
        _register_font_file(path)
        return path, _read_font_family(path)
    if DEFAULT_FONT_PATH.exists():
        _register_font_file(DEFAULT_FONT_PATH)
        return DEFAULT_FONT_PATH, fallback
    return None, fallback


def default_theme() -> GameTheme:
    cards = CardArt(
        normal=("#3a3228", "#d4b483", "#f7edd8"),
        heal=("#1e3d2a", "#6ecf8a", "#d8ffe6"),
        heavy_hit=("#4a241c", "#e07a5f", "#ffe4d8"),
        steal=("#2e2240", "#c9a0dc", "#f3e6ff"),
        disabled=("#2a302c", "#6a736c", "#8a948c"),
        selected=("#3d5a45", "#f0c674", "#fff6d8"),
    )
    return _build_theme(
        name="Default",
        font_path=DEFAULT_FONT_PATH if DEFAULT_FONT_PATH.exists() else None,
        font_family="Minecraft",
        screen_bg="#1a1f1c",
        win_bg="#1f5a32",
        lose_bg="#6b1f1f",
        title_fg="#f2e9d8",
        body_fg="#d7d2c4",
        log_bg="#121612",
        log_fg="#c8e6c0",
        overlay_bg="#1a1f1c",
        panel_bg="#222824",
        panel_border="#c4b59a",
        target_bg="#222824",
        cards=cards,
        scale_hue=130 / 360,
        card_style="pixel",
    )


def creative_theme_presets() -> list[GameTheme]:
    """Hand-crafted themes with distinct card frame art styles."""
    presets: list[GameTheme] = []

    neon_font = _theme_font("PressStart2P-Regular.ttf", "Minecraft")
    presets.append(
        _build_theme(
            name="Neon City",
            font_path=neon_font[0],
            font_family=neon_font[1],
            screen_bg="#0a0618",
            win_bg="#0d3d2a",
            lose_bg="#4a0828",
            title_fg="#ff71ce",
            body_fg="#05d9e8",
            log_bg="#12082a",
            log_fg="#01ff70",
            overlay_bg="#0a0618",
            panel_bg="#160c32",
            panel_border="#05d9e8",
            target_bg="#160c32",
            cards=CardArt(
                normal=("#12082a", "#ff71ce", "#fff0fa"),
                heal=("#0a1828", "#01ff70", "#d8ffe8"),
                heavy_hit=("#281008", "#fffb96", "#fffde0"),
                steal=("#180828", "#bd93f9", "#f3e6ff"),
                disabled=("#181028", "#5a5080", "#9088a8"),
                selected=("#1a0838", "#05d9e8", "#e0ffff"),
            ),
            scale_hue=300 / 360,
            card_style="neon",
            hud_active=("#1a0838", "#05d9e8", "#e0ffff"),
            hud_idle=("#12082a", "#bd93f9", "#d8c8f0"),
        )
    )

    presets.append(
        _build_theme(
            name="Volcanic Forge",
            font_path=DEFAULT_FONT_PATH if DEFAULT_FONT_PATH.exists() else None,
            font_family="Minecraft",
            screen_bg="#140808",
            win_bg="#2a5018",
            lose_bg="#6b1010",
            title_fg="#ffd080",
            body_fg="#ffb090",
            log_bg="#0c0404",
            log_fg="#ff9040",
            overlay_bg="#140808",
            panel_bg="#281010",
            panel_border="#ff6020",
            target_bg="#281010",
            cards=CardArt(
                normal=("#281008", "#ff6020", "#ffe0c8"),
                heal=("#102018", "#60c060", "#d0ffd0"),
                heavy_hit=("#381008", "#ff4020", "#ffe0d0"),
                steal=("#201028", "#c060ff", "#ecd0ff"),
                disabled=("#201818", "#705050", "#988880"),
                selected=("#401808", "#ffb040", "#fff0d0"),
            ),
            scale_hue=20 / 360,
            card_style="lava",
            hud_active=("#401808", "#ffb040", "#fff0d0"),
        )
    )

    presets.append(
        _build_theme(
            name="Frozen Tundra",
            font_path=DEFAULT_FONT_PATH if DEFAULT_FONT_PATH.exists() else None,
            font_family="Minecraft",
            screen_bg="#0c1828",
            win_bg="#1a4838",
            lose_bg="#482838",
            title_fg="#e8f8ff",
            body_fg="#b8d8f0",
            log_bg="#081420",
            log_fg="#a0e0ff",
            overlay_bg="#0c1828",
            panel_bg="#142838",
            panel_border="#80d0ff",
            target_bg="#142838",
            cards=CardArt(
                normal=("#183048", "#80d0ff", "#f0f8ff"),
                heal=("#103828", "#60e0a0", "#e0fff0"),
                heavy_hit=("#283848", "#a0e0ff", "#f0ffff"),
                steal=("#202848", "#a0b0ff", "#e8e8ff"),
                disabled=("#182028", "#607080", "#90a0b0"),
                selected=("#204058", "#c0f0ff", "#ffffff"),
            ),
            scale_hue=200 / 360,
            card_style="ice",
            hud_active=("#204058", "#c0f0ff", "#ffffff"),
        )
    )

    presets.append(
        _build_theme(
            name="Enchanted Grove",
            font_path=DEFAULT_FONT_PATH if DEFAULT_FONT_PATH.exists() else None,
            font_family="Minecraft",
            screen_bg="#101a12",
            win_bg="#1f5a32",
            lose_bg="#5a2818",
            title_fg="#e8ffe0",
            body_fg="#c8e8b8",
            log_bg="#0a120a",
            log_fg="#90e878",
            overlay_bg="#101a12",
            panel_bg="#1a2820",
            panel_border="#78c860",
            target_bg="#1a2820",
            cards=CardArt(
                normal=("#243820", "#a0d878", "#f0ffe8"),
                heal=("#1a3828", "#60e090", "#e0ffe8"),
                heavy_hit=("#382818", "#e09060", "#ffe8d8"),
                steal=("#282038", "#b090e0", "#f0e8ff"),
                disabled=("#202820", "#688068", "#90a890"),
                selected=("#2a4828", "#f0d060", "#fffae0"),
            ),
            scale_hue=120 / 360,
            card_style="pixel",
        )
    )

    shadow_font = _theme_font("Creepster-Regular.ttf", "Minecraft")
    presets.append(
        _build_theme(
            name="Shadow Realm",
            font_path=shadow_font[0],
            font_family=shadow_font[1],
            screen_bg="#060608",
            win_bg="#1a3020",
            lose_bg="#401018",
            title_fg="#c8b0e0",
            body_fg="#9080a8",
            log_bg="#040406",
            log_fg="#8060b0",
            overlay_bg="#060608",
            panel_bg="#100c18",
            panel_border="#6040a0",
            target_bg="#100c18",
            cards=CardArt(
                normal=("#100c14", "#8060b0", "#e0d0f0"),
                heal=("#0c1410", "#508060", "#c0e0c8"),
                heavy_hit=("#180c10", "#b05080", "#f0d0e0"),
                steal=("#140c20", "#9060c0", "#e8d8ff"),
                disabled=("#0c0c10", "#484058", "#686070"),
                selected=("#201030", "#a080d0", "#f0e8ff"),
            ),
            scale_hue=270 / 360,
            card_style="shadow",
            hud_active=("#201030", "#a080d0", "#f0e8ff"),
        )
    )

    arcade_font = _theme_font("PressStart2P-Regular.ttf", "Minecraft")
    presets.append(
        _build_theme(
            name="Arcade Cabinet",
            font_path=arcade_font[0],
            font_family=arcade_font[1],
            screen_bg="#101028",
            win_bg="#006040",
            lose_bg="#880018",
            title_fg="#ffff00",
            body_fg="#00ffff",
            log_bg="#080818",
            log_fg="#ff00ff",
            overlay_bg="#101028",
            panel_bg="#181840",
            panel_border="#ffff00",
            target_bg="#181840",
            cards=CardArt(
                normal=("#202050", "#ffff00", "#ffffe0"),
                heal=("#104030", "#00ff80", "#d0ffe8"),
                heavy_hit=("#502020", "#ff4040", "#ffe0e0"),
                steal=("#301050", "#ff80ff", "#ffe8ff"),
                disabled=("#202030", "#606080", "#9090a8"),
                selected=("#303070", "#00ffff", "#e0ffff"),
            ),
            scale_hue=60 / 360,
            card_style="arcade",
            hud_active=("#303070", "#00ffff", "#e0ffff"),
        )
    )

    presets.append(
        _build_theme(
            name="Royal Treasure",
            font_path=DEFAULT_FONT_PATH if DEFAULT_FONT_PATH.exists() else None,
            font_family="Minecraft",
            screen_bg="#181008",
            win_bg="#284018",
            lose_bg="#601818",
            title_fg="#ffe8a0",
            body_fg="#d8c090",
            log_bg="#100c04",
            log_fg="#f0c860",
            overlay_bg="#181008",
            panel_bg="#282010",
            panel_border="#e8b840",
            target_bg="#282010",
            cards=CardArt(
                normal=("#382818", "#e8b840", "#fff8e0"),
                heal=("#283820", "#80c060", "#e8ffe0"),
                heavy_hit=("#482018", "#e87840", "#ffe8d0"),
                steal=("#302040", "#c090e0", "#f0e8ff"),
                disabled=("#282018", "#706050", "#988878"),
                selected=("#483820", "#ffe060", "#fffff0"),
            ),
            scale_hue=45 / 360,
            card_style="gold",
            hud_active=("#483820", "#ffe060", "#fffff0"),
        )
    )

    circuit_font = _theme_font("RobotoMono-Regular.ttf", "Minecraft")
    presets.append(
        _build_theme(
            name="Cyber Grid",
            font_path=circuit_font[0],
            font_family=circuit_font[1],
            screen_bg="#041018",
            win_bg="#083828",
            lose_bg="#381018",
            title_fg="#40ffb0",
            body_fg="#80c0d0",
            log_bg="#020810",
            log_fg="#20e890",
            overlay_bg="#041018",
            panel_bg="#081820",
            panel_border="#20e890",
            target_bg="#081820",
            cards=CardArt(
                normal=("#0a2030", "#20e890", "#d0ffe8"),
                heal=("#082820", "#40ff90", "#d8ffe0"),
                heavy_hit=("#281808", "#ff8040", "#ffe8d0"),
                steal=("#180828", "#8040ff", "#ecd0ff"),
                disabled=("#101820", "#406060", "#608080"),
                selected=("#103028", "#60ffb0", "#e0fff0"),
            ),
            scale_hue=160 / 360,
            card_style="circuit",
            hud_active=("#103028", "#60ffb0", "#e0fff0"),
        )
    )

    presets.append(
        _build_theme(
            name="Stone Stronghold",
            font_path=DEFAULT_FONT_PATH if DEFAULT_FONT_PATH.exists() else None,
            font_family="Minecraft",
            screen_bg="#141412",
            win_bg="#283820",
            lose_bg="#502018",
            title_fg="#e0d8c8",
            body_fg="#b8b0a0",
            log_bg="#0c0c0a",
            log_fg="#c0b8a8",
            overlay_bg="#141412",
            panel_bg="#242220",
            panel_border="#908878",
            target_bg="#242220",
            cards=CardArt(
                normal=("#383430", "#a89878", "#f0ece0"),
                heal=("#283830", "#78a878", "#e0f0e0"),
                heavy_hit=("#483028", "#c08060", "#ffe8d8"),
                steal=("#383040", "#9888b0", "#ece8f0"),
                disabled=("#282824", "#686860", "#888880"),
                selected=("#484038", "#d0b870", "#fff8e0"),
            ),
            scale_hue=40 / 360,
            card_style="stone",
        )
    )

    return presets


CREATIVE_THEMES: list[GameTheme] = creative_theme_presets()


def _discover_fonts() -> list[Path]:
    if not FONT_DIR.exists():
        return [DEFAULT_FONT_PATH] if DEFAULT_FONT_PATH.exists() else []
    fonts = sorted(
        p
        for p in FONT_DIR.iterdir()
        if p.suffix.lower() in {".ttf", ".otf"} and p.name.lower() != "desktop.ini"
    )
    if DEFAULT_FONT_PATH.exists() and DEFAULT_FONT_PATH not in fonts:
        fonts.insert(0, DEFAULT_FONT_PATH)
    return fonts or ([DEFAULT_FONT_PATH] if DEFAULT_FONT_PATH.exists() else [])


def generate_random_theme(rng: random.Random | None = None) -> GameTheme:
    rng = rng or random.Random()
    fonts = _discover_fonts()
    font_path = rng.choice(fonts) if fonts else None
    if font_path and font_path.exists():
        _register_font_file(font_path)
        font_family = _read_font_family(font_path)
    else:
        font_family = "Minecraft"

    hue = rng.random()
    accent_hue = (hue + rng.uniform(0.12, 0.35)) % 1.0
    heal_hue = (hue + 0.33) % 1.0
    steal_hue = (hue + 0.62) % 1.0
    heavy_hue = (hue + 0.08) % 1.0

    screen_bg = _hsl_to_hex(hue, rng.uniform(0.18, 0.35), rng.uniform(0.08, 0.16))
    title_fg = _hsl_to_hex(hue, rng.uniform(0.15, 0.35), rng.uniform(0.82, 0.92))
    body_fg = _hsl_to_hex(hue, rng.uniform(0.12, 0.28), rng.uniform(0.68, 0.78))
    log_bg = _hsl_to_hex(hue, rng.uniform(0.2, 0.4), rng.uniform(0.05, 0.12))
    log_fg = _hsl_to_hex(accent_hue, rng.uniform(0.35, 0.55), rng.uniform(0.72, 0.85))
    panel_bg = _shift_hex(screen_bg, 14)
    panel_border = _hsl_to_hex(accent_hue, rng.uniform(0.25, 0.45), rng.uniform(0.62, 0.72))

    cards = CardArt(
        normal=_card_triplet(accent_hue, rng.uniform(0.28, 0.5), 0.22, 0.58, 0.88),
        heal=_card_triplet(heal_hue, rng.uniform(0.35, 0.55), 0.18, 0.52, 0.9),
        heavy_hit=_card_triplet(heavy_hue, rng.uniform(0.4, 0.6), 0.2, 0.55, 0.9),
        steal=_card_triplet(steal_hue, rng.uniform(0.3, 0.5), 0.18, 0.52, 0.9),
        disabled=_card_triplet(hue, 0.12, 0.16, 0.38, 0.52),
        selected=_card_triplet(accent_hue, rng.uniform(0.35, 0.55), 0.28, 0.62, 0.92),
    )
    hud_active = _card_triplet(accent_hue, rng.uniform(0.35, 0.55), 0.28, 0.62, 0.92)
    hud_idle = (
        _shift_hex(screen_bg, 18),
        _hsl_to_hex(hue, 0.12, 0.55),
        _hsl_to_hex(hue, 0.12, 0.72),
    )

    style = rng.choice(CARD_STYLES)

    return _build_theme(
        name=f"Random ({style})",
        font_path=font_path,
        font_family=font_family,
        screen_bg=screen_bg,
        win_bg=_hsl_to_hex(0.33, rng.uniform(0.35, 0.55), rng.uniform(0.22, 0.32)),
        lose_bg=_hsl_to_hex(0.02, rng.uniform(0.45, 0.65), rng.uniform(0.24, 0.34)),
        title_fg=title_fg,
        body_fg=body_fg,
        log_bg=log_bg,
        log_fg=log_fg,
        overlay_bg=screen_bg,
        panel_bg=panel_bg,
        panel_border=panel_border,
        target_bg=panel_bg,
        cards=cards,
        scale_hue=heal_hue,
        hud_active=hud_active,
        hud_idle=hud_idle,
        hud_dead=cards.disabled,
        target_self=hud_active,
        target_other=(
            _shift_hex(screen_bg, 12),
            panel_border,
            title_fg,
        ),
        card_style=style,
    )


def pick_creative_theme(rng: random.Random | None = None) -> GameTheme:
    rng = rng or random.Random()
    return rng.choice(CREATIVE_THEMES)


_ACTIVE: GameTheme = default_theme()


def active_theme() -> GameTheme:
    return _ACTIVE


def set_active_theme(theme: GameTheme) -> None:
    global _ACTIVE
    if theme.font_path and theme.font_path.exists():
        _register_font_file(theme.font_path)
    _ACTIVE = theme


def reset_theme() -> GameTheme:
    theme = default_theme()
    set_active_theme(theme)
    return theme


def randomize_theme(rng: random.Random | None = None) -> GameTheme:
    rng = rng or random.Random()
    theme = pick_creative_theme(rng) if rng.random() < 0.85 else generate_random_theme(rng)
    set_active_theme(theme)
    return theme
