#!/usr/bin/env python3
"""Crash Out — window (tkinter) UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

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
    TURN_DELAY_MS,
    Card,
    Player,
    bot_choose_play,
    check_winner,
    craft_card,
    describe_target,
    make_bot_deck,
    make_mercy_card,
    make_players,
    make_solo_players,
    next_alive_index,
    resolve_card,
)


class CrashOutApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Crash Out")
        self.geometry("820x640")
        self.minsize(720, 560)
        self.configure(bg="#1a1f1c")

        self.settings: MatchSettings | None = None
        self.players: list[Player] = []
        self.crafted: list[Card] = []
        self.craft_slot = 1
        self.active = 0
        self.pending_card: Card | None = None
        self.starting_hp = DEFAULT_STARTING_HP
        self._busy = False

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

        self.container = tk.Frame(self, bg="#1a1f1c")
        self.container.pack(fill="both", expand=True, padx=16, pady=16)
        self.show_setup()

    def clear(self) -> None:
        for w in self.container.winfo_children():
            w.destroy()

    def show_setup(self) -> None:
        self.clear()
        ttk.Label(self.container, text="CRASH OUT", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            self.container,
            text="Window mode — craft cards, then play hotseat or vs bot.",
            style="Body.TLabel",
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
        self.craft_slot = 1
        self.show_craft()

    def show_craft(self) -> None:
        assert self.settings is not None
        self.clear()
        if self.craft_slot >= DECK_SIZE:
            # Add Mercy then start match
            self.crafted.append(make_mercy_card(DECK_SIZE, self.crafted))
            self.start_match()
            return

        pp = self.settings.power_points
        ttk.Label(
            self.container,
            text=f"Card Lab — Card {self.craft_slot}/{DECK_SIZE}",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            self.container,
            text=f"Spend exactly {pp} power points (damage + heal).",
            style="Body.TLabel",
        ).pack(anchor="w", pady=(4, 12))

        self.damage_var = tk.IntVar(value=pp // 2)
        row = tk.Frame(self.container, bg="#1a1f1c")
        row.pack(fill="x", pady=8)
        ttk.Label(row, text="Damage points", style="Body.TLabel").pack(side="left")
        scale = ttk.Scale(
            row,
            from_=0,
            to=pp,
            orient="horizontal",
            command=self._on_damage_slide,
        )
        scale.set(pp // 2)
        scale.pack(side="left", fill="x", expand=True, padx=12)
        self.preview = ttk.Label(self.container, text="", style="Body.TLabel")
        self.preview.pack(anchor="w", pady=8)
        self._on_damage_slide(str(pp // 2))

        ttk.Button(
            self.container,
            text="Save card",
            style="Accent.TButton",
            command=self.save_crafted_card,
        ).pack(anchor="w", pady=16)

        if self.crafted:
            ttk.Label(self.container, text="Deck so far:", style="Body.TLabel").pack(
                anchor="w", pady=(8, 4)
            )
            for i, c in enumerate(self.crafted, start=1):
                ttk.Label(
                    self.container, text=f"  [{i}] {c.label()}", style="Body.TLabel"
                ).pack(anchor="w")

    def _on_damage_slide(self, value: str) -> None:
        assert self.settings is not None
        damage = int(float(value))
        heal = self.settings.power_points - damage
        self.damage_var.set(damage)
        preview = craft_card(self.craft_slot, damage, self.settings.power_points, self.crafted)
        self.preview.configure(
            text=f"Preview: {preview.name} — {damage} dmg / {heal} heal"
        )

    def save_crafted_card(self) -> None:
        assert self.settings is not None
        damage = self.damage_var.get()
        card = craft_card(
            self.craft_slot, damage, self.settings.power_points, self.crafted
        )
        self.crafted.append(card)
        self.craft_slot += 1
        self.show_craft()

    def start_match(self) -> None:
        assert self.settings is not None
        if self.settings.vs_bot:
            bot_deck = make_bot_deck(self.settings.power_points)
            self.players = make_solo_players(
                self.crafted, bot_deck, self.settings.starting_hp
            )
        else:
            self.players = make_players(
                self.settings.player_count,
                self.crafted,
                self.settings.starting_hp,
            )
        self.active = 0
        self.pending_card = None
        self.show_play(f"Match started. {self.players[0].name}'s turn.")

    def show_play(self, banner_msg: str = "") -> None:
        self.clear()
        self._busy = False
        player = self.players[self.active]

        ttk.Label(self.container, text="CRASH OUT", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            self.container,
            text=banner_msg or f"Turn — {player.name}",
            style="Body.TLabel",
        ).pack(anchor="w", pady=(2, 10))

        status = tk.Frame(self.container, bg="#243028", padx=10, pady=8)
        status.pack(fill="x", pady=(0, 10))
        for i, p in enumerate(self.players):
            mark = "  << active" if i == self.active else ""
            text = (
                f"{p.name}: OUT{mark}"
                if not p.alive
                else f"{p.name}: {p.hp}/{p.max_hp} HP{mark}"
            )
            color = "#f0c674" if i == self.active else "#d7d2c4"
            tk.Label(
                status,
                text=text,
                fg=color,
                bg="#243028",
                font=("Segoe UI", 11, "bold" if i == self.active else "normal"),
            ).pack(anchor="w")

        self.log = tk.Text(
            self.container,
            height=8,
            bg="#121612",
            fg="#c8e6c0",
            insertbackground="#c8e6c0",
            font=("Consolas", 10),
            relief="flat",
            wrap="word",
        )
        self.log.pack(fill="both", expand=False, pady=(0, 10))
        self.log.insert("end", "Play a card, then choose a target.\n")
        self.log.configure(state="disabled")

        action = tk.Frame(self.container, bg="#1a1f1c")
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
        hand = tk.Frame(action, bg="#1a1f1c")
        hand.pack(fill="x", pady=6)
        for card in player.hand:
            cooling = card.id == player.last_card_id
            text = card.label()
            if cooling:
                text += "  [cooling down]"
            btn = ttk.Button(
                hand,
                text=text,
                command=(lambda c=card: self.pick_card(c)),
            )
            btn.pack(fill="x", pady=3)
            if cooling:
                btn.state(["disabled"])

        self.target_frame = tk.Frame(action, bg="#1a1f1c")
        self.target_frame.pack(fill="x", pady=(12, 0))

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def pick_card(self, card: Card) -> None:
        if self._busy:
            return
        player = self.players[self.active]
        if card.id == player.last_card_id:
            return
        self.pending_card = card
        for w in self.target_frame.winfo_children():
            w.destroy()
        ttk.Label(
            self.target_frame,
            text=f"Target for {card.name}:",
            style="Body.TLabel",
        ).pack(anchor="w")
        for i, p in enumerate(self.players):
            if not p.alive:
                continue
            label = describe_target(card, self.players, self.active, i)
            ttk.Button(
                self.target_frame,
                text=f"{p.name} ({p.hp}/{p.max_hp}) — {label}",
                command=(lambda idx=i: self.confirm_play(idx)),
            ).pack(fill="x", pady=3)

    def confirm_play(self, target_idx: int) -> None:
        if self._busy or self.pending_card is None:
            return
        self._busy = True
        card = self.pending_card
        player = self.players[self.active]
        player.last_card_id = card.id
        self.append_log(f"{player.name} plays {card.name}")
        self.append_log(
            f"Target: {describe_target(card, self.players, self.active, target_idx)}"
        )
        for line in resolve_card(card, self.players, self.active, target_idx):
            self.append_log("  " + line)
        self.pending_card = None
        self.after(TURN_DELAY_MS, self.after_resolve)

    def run_bot_turn(self) -> None:
        player = self.players[self.active]
        choice = bot_choose_play(self.players, self.active, self.starting_hp)
        if choice is None:
            player.last_card_id = None
            self.append_log("Bot has no playable cards — skipped.")
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
