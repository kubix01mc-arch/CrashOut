#!/usr/bin/env python3
"""Crash Out — window (tkinter) UI."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageTk

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from CrashOut_Resources import (
    DEFAULT_POWER_POINTS,
    DEFAULT_STARTING_HP,
    DECK_SIZE,
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
    archetype_taken,
    bot_choose_play,
    can_add_heavy_hit_card,
    can_add_steal_card,
    can_craft_steal,
    card_is_cooling,
    check_winner,
    craft_card,
    deck_has_heavy_hit,
    deck_has_steal,
    describe_target,
    effective_card_stats,
    make_bot_deck,
    make_mercy_card,
    make_players_from_mixed_decks,
    make_solo_players,
    name_for_split,
    next_alive_index,
    resolve_card,
    resolve_steal,
    return_expired_borrows,
    stat_budget,
    tick_turn_cooldowns,
)

# Playing-card style buttons: width:height = 5:7
CARD_ASPECT = 7 / 5
CARD_MIN_W = 48
CARD_MAX_W = 200
CARD_GAP_MIN = 6
TARGET_MIN = 100
TARGET_MAX = 200
LOG_PANEL_WIDTH = 300
BOT_ICON_PATH = Path(__file__).resolve().parent / "assets" / "bot_icon.png"


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


def _rounded_rect_points(x1: int, y1: int, x2: int, y2: int, r: int) -> list[int]:
    """Point list for a smooth rounded rectangle polygon."""
    r = min(r, (x2 - x1) // 2, (y2 - y1) // 2)
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]


class RoundedCardButton(tk.Canvas):
    """Clickable rounded-rectangle card face (5:7 aspect ratio)."""

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
            bg="#1a1f1c",
            highlightthickness=0,
            bd=0,
            cursor="arrow" if disabled else "hand2",
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

    def _radius(self) -> int:
        return max(6, min(self._width, self._height) // 8)

    def _font(self, ratio: float, minimum: int = 7) -> tuple[str, int, str]:
        size = max(minimum, int(min(self._width, self._height) * ratio))
        return ("Segoe UI", size, "bold")

    def _font_regular(self, ratio: float, minimum: int = 7) -> tuple[str, int]:
        size = max(minimum, int(min(self._width, self._height) * ratio))
        return ("Segoe UI", size)

    def _fill_colors(self) -> tuple[str, str, str]:
        if self.disabled:
            return "#2a302c", "#5a635c", "#7a847c"
        if self.selected:
            return "#3d5a45", "#f0c674", "#f7f0e0"
        if self.card.heal_any:
            return "#2e4a3a", "#8fd6a8", "#e8f8ee"
        return "#2c3330", "#c4b59a", "#f2e9d8"

    def _draw(self, hover: bool = False) -> None:
        self.delete("all")
        fill, accent, text_color = self._fill_colors()
        if hover and not self.disabled:
            fill = "#3a4540"
        pad = max(2, self._width // 36)
        x1, y1 = pad, pad
        x2, y2 = self._width - pad, self._height - pad
        radius = self._radius()
        points = _rounded_rect_points(x1, y1, x2, y2, radius)
        self.create_polygon(
            points,
            smooth=True,
            splinesteps=12,
            fill=fill,
            outline=accent,
            width=max(1, self._width // 55),
        )
        inset = max(3, self._width // 22)
        inner = _rounded_rect_points(
            x1 + inset, y1 + inset, x2 - inset, y2 - inset, max(4, radius - 4)
        )
        self.create_polygon(
            inner,
            smooth=True,
            splinesteps=12,
            fill="",
            outline=accent,
            width=1,
        )

        cx = self._width // 2
        title_y = int(self._height * 0.18)
        stats_y = int(self._height * 0.52)
        detail_y = int(self._height * 0.84)
        self.create_text(
            cx,
            title_y,
            text=self.card.name,
            fill=text_color,
            font=self._font(0.11, 8),
            width=self._width - max(12, self._width // 6),
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
            font=self._font(0.14, 10),
            justify="center",
        )
        self.create_text(
            cx,
            detail_y,
            text=detail,
            fill=text_color,
            font=self._font_regular(0.08, 7),
            width=self._width - max(10, self._width // 7),
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
            bg="#222824",
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
        if self.is_self:
            fill = "#3d5a45" if not hover else "#4a6b52"
            accent, text = "#f0c674", "#f7f0e0"
        else:
            fill = "#2c3330" if not hover else "#3a4540"
            accent, text = "#c4b59a", "#f2e9d8"
        return fill, accent, text

    def _draw_badge(self, cx: int, cy: int, accent: str, text_color: str) -> None:
        if self.player.is_bot and self._bot_photo_getter is not None:
            icon_size = max(32, int(self._size * 0.42))
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
            font=("Segoe UI", max(18, self._size // 3), "bold"),
            justify="center",
        )

    def _draw(self, hover: bool = False) -> None:
        self.delete("all")
        fill, accent, text_color = self._colors(hover)
        s = self._size
        pad = max(3, s // 24)
        radius = max(10, s // 6)
        points = _rounded_rect_points(pad, pad, s - pad, s - pad, radius)
        self.create_polygon(
            points,
            smooth=True,
            splinesteps=12,
            fill=fill,
            outline=accent,
            width=max(1, s // 50),
        )
        cx = s // 2
        self._draw_badge(cx, int(s * 0.34), accent, text_color)
        self.create_text(
            cx,
            int(s * 0.62),
            text=f"{self.player.hp}/{self.player.max_hp}",
            fill=accent,
            font=("Segoe UI", max(10, s // 9), "bold"),
            justify="center",
        )
        self.create_text(
            cx,
            int(s * 0.82),
            text=self.subtitle,
            fill=text_color,
            font=("Segoe UI", max(7, s // 14)),
            width=s - pad * 4,
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


class CrashOutApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Crash Out")
        self.geometry("920x700")
        self.minsize(480, 400)
        self.configure(bg="#1a1f1c")
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
        self._overlay_host = tk.Frame(self, bg="#1a1f1c")
        self._target_overlay: tk.Canvas | None = None
        self._craft_scale: ttk.Scale | None = None
        self._target_row: tk.Frame | None = None
        self._target_buttons: list[RoundedTargetButton] = []
        self._bot_photo_cache: dict[int, tk.PhotoImage] = {}
        self.preview: ttk.Label | None = None
        self.save_btn: ttk.Button | None = None

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure(
            "Title.TLabel",
            font=("Segoe UI", 22, "bold"),
            foreground="#f2e9d8",
            background="#1a1f1c",
        )
        self.style.configure(
            "Body.TLabel",
            font=("Segoe UI", 11),
            foreground="#d7d2c4",
            background="#1a1f1c",
        )
        self.style.configure(
            "Log.TLabel",
            font=("Consolas", 10),
            foreground="#c8e6c0",
            background="#121612",
        )
        self.style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"))
        self.style.configure(
            "Green.Horizontal.TScale",
            troughcolor="#243028",
            background="#6ecf8a",
            bordercolor="#4a9e62",
            lightcolor="#8fd6a8",
            darkcolor="#3d8b52",
        )
        self.style.map(
            "Green.Horizontal.TScale",
            background=[("active", "#8fd6a8"), ("!disabled", "#6ecf8a")],
        )

        self.container = tk.Frame(self, bg="#1a1f1c")
        self.container.pack(fill="both", expand=True, padx=16, pady=16)
        self.show_setup()

    def _toggle_fullscreen(self, _event: tk.Event | None = None) -> str:
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)
        return "break"

    def _raise_overlay_layer(self) -> None:
        self._overlay_host.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.container.lower(self._overlay_host)
        tk.Misc.tkraise(self._overlay_host)

    def clear(self) -> None:
        self._hide_target_overlay()
        self._card_faces = []
        self._hand_outer = None
        self.preview = None
        self.save_btn = None
        for w in self.container.winfo_children():
            w.destroy()

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
        if self._target_overlay is not None:
            self._target_overlay.destroy()
        self._target_overlay = None
        self._target_row = None
        self._target_buttons = []
        self._overlay_host.place_forget()

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
        self._hide_target_overlay()
        self._raise_overlay_layer()
        self._target_overlay = tk.Canvas(
            self._overlay_host,
            highlightthickness=0,
            bd=0,
            bg="#1a1f1c",
        )
        self._target_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._target_overlay.bind("<Configure>", self._draw_target_dim)
        self.after_idle(self._draw_target_dim)

        panel = tk.Frame(
            self._overlay_host,
            bg="#222824",
            highlightbackground="#c4b59a",
            highlightthickness=2,
            padx=20,
            pady=16,
        )
        panel.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            panel,
            text=f"Choose target for {card.name}",
            fg="#f2e9d8",
            bg="#222824",
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=(0, 12))

        self._target_row = tk.Frame(panel, bg="#222824", width=560, height=220)
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
        self.clear()
        ttk.Label(self.container, text="CRASH OUT", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            self.container,
            text=(
                "Window mode — craft cards, then play hotseat or vs bot. "
                "In multiplayer, each player builds a deck; craftable cards are then "
                "shuffled and re-dealt (Mercy and steal stay with their owner)."
            ),
            style="Body.TLabel",
            wraplength=860,
        ).pack(anchor="w", pady=(4, 16))

        form = tk.Frame(self.container, bg="#1a1f1c")
        form.pack(fill="x")

        self.mode_var = tk.StringVar(value="1")
        ttk.Label(form, text="Match size", style="Body.TLabel").grid(
            row=0, column=0, sticky="w", pady=6
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
            width=22,
        )
        modes.current(0)
        modes.grid(row=0, column=1, sticky="w", padx=8)

        self.hp_var = tk.StringVar(value=str(DEFAULT_STARTING_HP))
        ttk.Label(form, text="Starting HP", style="Body.TLabel").grid(
            row=1, column=0, sticky="w", pady=6
        )
        ttk.Entry(form, textvariable=self.hp_var, width=12).grid(
            row=1, column=1, sticky="w", padx=8
        )

        self.pp_var = tk.StringVar(value=str(DEFAULT_POWER_POINTS))
        ttk.Label(form, text="Power points / card", style="Body.TLabel").grid(
            row=2, column=0, sticky="w", pady=6
        )
        ttk.Entry(form, textvariable=self.pp_var, width=12).grid(
            row=2, column=1, sticky="w", padx=8
        )

        ttk.Label(
            self.container,
            text=f"Max HP = 2× starting. Card 5 = Mercy ({FIFTH_CARD_HEAL} heal any target).",
            style="Body.TLabel",
        ).pack(anchor="w", pady=(18, 8))

        ttk.Button(
            self.container,
            text="Continue to Card Lab",
            style="Accent.TButton",
            command=self.begin_card_lab,
        ).pack(anchor="w", pady=12)

    def begin_card_lab(self) -> None:
        try:
            hp = int(self.hp_var.get().strip())
            pp = int(self.pp_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "HP and power points must be numbers.")
            return
        if not (HP_MIN <= hp <= HP_MAX):
            messagebox.showerror("Invalid HP", f"Starting HP must be {HP_MIN}-{HP_MAX}.")
            return
        if not (PP_MIN <= pp <= PP_MAX):
            messagebox.showerror(
                "Invalid PP", f"Power points must be {PP_MIN}-{PP_MAX}."
            )
            return

        mode = self.mode_var.get()
        count = int(mode[0])
        self.settings = MatchSettings(count, hp, pp)
        self.starting_hp = hp
        self.crafted = []
        self.all_player_decks = []
        self.crafting_player = 1
        self.craft_slot = 1
        self.show_craft()

    def show_craft(self) -> None:
        assert self.settings is not None
        self.clear()
        if self.craft_slot >= DECK_SIZE:
            self.crafted.append(make_mercy_card(DECK_SIZE, self.crafted))
            if self.settings.vs_bot:
                self.start_match()
            else:
                self._finish_player_craft()
            return

        pp = self.settings.power_points
        if self.settings.vs_bot:
            lab_title = f"Card Lab — Card {self.craft_slot}/{DECK_SIZE}"
            lab_hint = (
                f"Spend exactly {pp} power points (damage + heal)."
            )
        else:
            lab_title = (
                f"Card Lab — player-{self.crafting_player} "
                f"— Card {self.craft_slot}/{DECK_SIZE}"
            )
            lab_hint = (
                f"player-{self.crafting_player}, spend exactly {pp} power points "
                f"(damage + heal). Craftable cards are shuffled and re-dealt when "
                f"everyone is done. Mercy and steal stay with their owner."
            )
        ttk.Label(
            self.container,
            text=lab_title,
            style="Title.TLabel",
        ).pack(anchor="w")
        steal_hint = (
            f" Optional: one steal card per deck ({STEAL_PP_COST} PP), "
            "or one Heavy Hit (+50% power, clears target cooldowns 2 turns)."
            if (can_craft_steal(pp) or can_add_heavy_hit_card(self.crafted))
            and not self.settings.vs_bot
            else (
                " Optional: one Heavy Hit per deck (+50% power, clears target cooldowns 2 turns)."
                if can_add_heavy_hit_card(self.crafted)
                else ""
            )
        )
        ttk.Label(
            self.container,
            text=(
                f"{lab_hint}{steal_hint} "
                "No duplicate types (Sanctuary / Caretaker / Allrounder / Bruiser / Wrecker)."
            ),
            style="Body.TLabel",
            wraplength=860,
        ).pack(anchor="w", pady=(4, 12))

        self.steal_var = tk.BooleanVar(value=False)
        self.heavy_hit_var = tk.BooleanVar(value=False)
        if can_add_steal_card(self.crafted, pp) and not self.settings.vs_bot:
            ttk.Checkbutton(
                self.container,
                text=(
                    f"Steal ability ({STEAL_PP_COST} PP) — "
                    "steal 1 opponent card for 1 turn (one per deck)"
                ),
                variable=self.steal_var,
                command=self._on_steal_toggle,
            ).pack(anchor="w", pady=(0, 4))
        elif deck_has_steal(self.crafted):
            ttk.Label(
                self.container,
                text="Steal already used in this deck (one per deck).",
                style="Body.TLabel",
            ).pack(anchor="w", pady=(0, 4))

        if can_add_heavy_hit_card(self.crafted):
            ttk.Checkbutton(
                self.container,
                text=(
                    "Heavy Hit — +50% damage/heal, clears target cooldowns for "
                    "2 turns (one per deck)"
                ),
                variable=self.heavy_hit_var,
                command=self._on_heavy_hit_toggle,
            ).pack(anchor="w", pady=(0, 8))
        elif deck_has_heavy_hit(self.crafted):
            ttk.Label(
                self.container,
                text="Heavy Hit already used in this deck (one per deck).",
                style="Body.TLabel",
            ).pack(anchor="w", pady=(0, 8))

        budget = stat_budget(pp, self.steal_var.get())
        self.damage_var = tk.IntVar(value=budget // 2 if budget else 0)
        row = tk.Frame(self.container, bg="#1a1f1c")
        row.pack(fill="x", pady=8)
        ttk.Label(row, text="Damage points", style="Body.TLabel").pack(side="left")
        self._craft_scale = ttk.Scale(
            row,
            from_=0,
            to=max(0, budget),
            orient="horizontal",
            style="Green.Horizontal.TScale",
            command=self._on_damage_slide,
        )
        self._craft_scale.pack(side="left", fill="x", expand=True, padx=12)
        self.preview = ttk.Label(self.container, text="", style="Body.TLabel")
        self.preview.pack(anchor="w", pady=8)
        self.save_btn = ttk.Button(
            self.container,
            text="Save card",
            style="Accent.TButton",
            command=self.save_crafted_card,
        )
        self.save_btn.pack(anchor="w", pady=16)
        if budget:
            self._craft_scale.set(budget // 2)
        else:
            self._on_damage_slide("0")

        if self.crafted:
            ttk.Label(self.container, text="Deck so far:", style="Body.TLabel").pack(
                anchor="w", pady=(8, 4)
            )
            for i, c in enumerate(self.crafted, start=1):
                ttk.Label(
                    self.container, text=f"  [{i}] {c.label()}", style="Body.TLabel"
                ).pack(anchor="w")

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
        save_ok = self.save_btn is not None and self.save_btn.winfo_exists()
        if not preview_ok or not save_ok:
            return
        budget = self._craft_budget()
        damage = int(float(value))
        damage = max(0, min(budget, damage))
        heal = budget - damage
        self.damage_var.set(damage)
        archetype = name_for_split(damage, heal, budget if budget else 1)
        if self.heavy_hit_var.get():
            eff_dmg, eff_heal = effective_card_stats(
                Card(0, "Heavy Hit", damage, heal, heavy_hit=True)
            )
            preview_name = f"Heavy Hit — {eff_dmg} dmg / {eff_heal} heal (+50%)"
        else:
            preview_name = f"{archetype} — {damage} dmg / {heal} heal"
            if self.steal_var.get():
                preview_name += " + steal"
        if archetype_taken(
            "Heavy Hit" if self.heavy_hit_var.get() else archetype, self.crafted
        ):
            self.preview.configure(
                text=f"Preview: {preview_name} (already in deck — pick another split)"
            )
            self.save_btn.state(["disabled"])
        else:
            self.preview.configure(text=f"Preview: {preview_name}")
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
            bot_deck = make_bot_deck(self.settings.power_points)
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

    def _build_log_panel(self, parent: tk.Misc) -> None:
        panel = tk.Frame(
            parent,
            bg="#121612",
            width=LOG_PANEL_WIDTH,
            highlightbackground="#3a4540",
            highlightthickness=1,
        )
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)

        tk.Label(
            panel,
            text="Game Log",
            fg="#c8e6c0",
            bg="#121612",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))

        log_frame = tk.Frame(panel, bg="#121612")
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        scrollbar = tk.Scrollbar(log_frame, bg="#243028", troughcolor="#121612")
        scrollbar.pack(side="right", fill="y")

        self.log = tk.Text(
            log_frame,
            bg="#121612",
            fg="#c8e6c0",
            insertbackground="#c8e6c0",
            font=("Consolas", 10),
            relief="flat",
            wrap="word",
            state="disabled",
            yscrollcommand=scrollbar.set,
            padx=8,
            pady=8,
        )
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log.yview)
        self._render_game_log()

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
        self.clear()
        self._busy = False
        self.log = None
        player = self.players[self.active]
        if not self._game_log:
            self._game_log.append("Play a card, then choose a target.")
        self._log_turn_banner(banner_msg or f"Turn — {player.name}")

        hud_outer = tk.Frame(self.container, bg="#1a1f1c")
        hud_outer.pack(fill="x", pady=(0, 10))
        health_bar = tk.Frame(
            hud_outer,
            bg="#243028",
            padx=18,
            pady=10,
            highlightbackground="#4a5a50",
            highlightthickness=1,
        )
        health_bar.pack(anchor="center")
        for i, p in enumerate(self.players):
            chip = tk.Frame(health_bar, bg="#243028")
            chip.pack(side="left", padx=10)
            name_color = "#f0c674" if i == self.active else "#b8c4bc"
            hp_color = "#f2e9d8" if p.alive else "#8a948c"
            tk.Label(
                chip,
                text=p.name + ("  <<" if i == self.active else ""),
                fg=name_color,
                bg="#243028",
                font=("Segoe UI", 10, "bold" if i == self.active else "normal"),
            ).pack()
            tk.Label(
                chip,
                text=f"{p.hp}/{p.max_hp} HP" if p.alive else "OUT",
                fg=hp_color,
                bg="#243028",
                font=("Segoe UI", 16, "bold"),
            ).pack()

        body = tk.Frame(self.container, bg="#1a1f1c")
        body.pack(fill="both", expand=True)

        play_area = tk.Frame(body, bg="#1a1f1c")
        play_area.pack(side="left", fill="both", expand=True, padx=(0, 12))

        ttk.Label(play_area, text="CRASH OUT", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            play_area,
            text=banner_msg or f"Turn — {player.name}",
            style="Body.TLabel",
        ).pack(anchor="w", pady=(2, 10))

        self._build_log_panel(body)

        action = tk.Frame(play_area, bg="#1a1f1c")
        action.pack(fill="both", expand=True)

        if not player.alive:
            self.after(TURN_DELAY_MS, self.advance_turn)
            return

        if player.is_bot:
            ttk.Label(
                action, text="Bot is thinking...", style="Body.TLabel"
            ).pack(anchor="w")
            self.after(TURN_DELAY_MS, self.run_bot_turn)
            return

        ttk.Label(action, text="Your hand", style="Body.TLabel").pack(anchor="w")
        self._hand_outer = tk.Frame(action, bg="#1a1f1c")
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
        player.last_card_id = card.id
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
            self.after(TURN_DELAY_MS, self.after_resolve)
            return
        card, target_idx, reason = choice
        player.last_card_id = card.id
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
        self.clear()
        ttk.Label(self.container, text="Game Over", style="Title.TLabel").pack(
            anchor="w"
        )
        msg = f"{winner} wins!" if winner else "No one left standing."
        ttk.Label(self.container, text=msg, style="Body.TLabel").pack(
            anchor="w", pady=12
        )
        for p in self.players:
            status = "OUT" if not p.alive else f"{p.hp}/{p.max_hp} HP"
            ttk.Label(
                self.container, text=f"{p.name}: {status}", style="Body.TLabel"
            ).pack(anchor="w")
        ttk.Button(
            self.container,
            text="Play again",
            style="Accent.TButton",
            command=self.show_setup,
        ).pack(anchor="w", pady=16)
        ttk.Button(self.container, text="Quit", command=self.destroy).pack(anchor="w")


def main() -> None:
    app = CrashOutApp()
    app.mainloop()


if __name__ == "__main__":
    main()
