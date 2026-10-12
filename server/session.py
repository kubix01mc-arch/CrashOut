"""Authoritative match session for browser / LAN Crash Out."""

from __future__ import annotations

import copy
import secrets
import string
from dataclasses import dataclass, field
from typing import Any

from CrashOut_Resources import (
    BOT_NAME,
    DECK_SIZE,
    DECK_SIZE_MAX,
    DECK_SIZE_MIN,
    DEFAULT_POWER_POINTS,
    DEFAULT_STARTING_HP,
    FIFTH_CARD_HEAL,
    HP_MAX,
    HP_MIN,
    MAX_UNIQUE_CARDS_IN_DECK,
    PLAYER_COUNT_MAX,
    PP_MAX,
    PP_MIN,
    ActiveBorrow,
    Card,
    MatchSettings,
    Player,
    allows_duplicate_archetypes,
    bot_choose_play,
    can_add_heavy_hit_card,
    can_add_poison_card,
    can_add_shield_card,
    can_add_steal_card,
    can_add_vampire_card,
    card_is_cooling,
    card_to_dict,
    check_winner,
    clamp_deck_size,
    craft_card,
    make_bot_deck,
    make_mercy_card,
    make_players_from_mixed_decks,
    make_solo_players,
    mark_card_played,
    next_alive_index,
    resolve_card,
    resolve_steal,
    return_expired_borrows,
    stat_budget,
    tick_poisons_on_turn_start,
    tick_reaper_marks,
    tick_turn_cooldowns,
    unique_card_total,
)


def _room_code(n: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(n))


def _token() -> str:
    return secrets.token_urlsafe(16)


def _public_card(card: Card, *, cooling: bool = False) -> dict[str, Any]:
    data = card_to_dict(card)
    data["id"] = card.id
    data["cooldown_remaining"] = int(card.cooldown_remaining)
    data["cooling"] = cooling
    data["borrowed"] = bool(card.is_borrowed)
    data["effect"] = card.effect
    dmg = int(card.damage)
    heal = int(card.heal)
    if card.heavy_hit:
        from CrashOut_Resources import effective_card_stats

        dmg, heal = effective_card_stats(card)
    data["display_damage"] = dmg
    data["display_heal"] = heal
    return data


@dataclass
class Seat:
    seat: int
    name: str
    token: str
    ready: bool = False
    deck: list[Card] = field(default_factory=list)


@dataclass
class MatchSession:
    code: str = field(default_factory=_room_code)
    host_token: str = field(default_factory=_token)
    phase: str = "lobby"  # lobby | craft | play | game_over
    settings: MatchSettings = field(
        default_factory=lambda: MatchSettings(
            player_count=2,
            starting_hp=DEFAULT_STARTING_HP,
            power_points=DEFAULT_POWER_POINTS,
            deck_size=DECK_SIZE,
        )
    )
    seats: dict[int, Seat] = field(default_factory=dict)
    players: list[Player] = field(default_factory=list)
    active: int = 0
    borrows: list[ActiveBorrow] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    winner_name: str | None = None
    pending_card_id: int | None = None

    @property
    def vs_bot(self) -> bool:
        return self.settings.player_count == 1

    def seat_by_token(self, token: str) -> Seat | None:
        for seat in self.seats.values():
            if seat.token == token:
                return seat
        return None

    def set_settings(
        self,
        *,
        player_count: int,
        starting_hp: int,
        power_points: int,
        deck_size: int,
        host_token: str,
    ) -> None:
        if host_token != self.host_token:
            raise PermissionError("Only the host can change settings.")
        if self.phase != "lobby":
            raise RuntimeError("Settings are locked after the lobby.")
        if not (1 <= player_count <= PLAYER_COUNT_MAX):
            raise ValueError(f"Players must be 1-{PLAYER_COUNT_MAX} (1 = vs bot).")
        if not (HP_MIN <= starting_hp <= HP_MAX):
            raise ValueError(f"HP must be {HP_MIN}-{HP_MAX}.")
        if not (PP_MIN <= power_points <= PP_MAX):
            raise ValueError(f"PP must be {PP_MIN}-{PP_MAX}.")
        deck_size = clamp_deck_size(deck_size)
        if not (DECK_SIZE_MIN <= deck_size <= DECK_SIZE_MAX):
            raise ValueError(f"Deck size must be {DECK_SIZE_MIN}-{DECK_SIZE_MAX}.")
        self.settings = MatchSettings(player_count, starting_hp, power_points, deck_size)
        # Drop seats that no longer fit (bot mode only keeps seat 0).
        capacity = 1 if self.vs_bot else player_count
        for seat in list(self.seats):
            if seat >= capacity:
                del self.seats[seat]

    def join(self, name: str, preferred_seat: int | None = None) -> Seat:
        if self.phase != "lobby":
            raise RuntimeError("This room is no longer accepting players.")
        if self.vs_bot and len(self.seats) >= 1 and preferred_seat != 0:
            raise RuntimeError("This is a vs-bot room — only the host plays.")
        name = (name or "").strip()[:20] or "Player"
        capacity = 1 if self.vs_bot else self.settings.player_count
        if preferred_seat is not None and preferred_seat in self.seats:
            raise ValueError("That seat is taken.")
        if preferred_seat is not None and not (0 <= preferred_seat < capacity):
            raise ValueError("Invalid seat.")
        if preferred_seat is None:
            free = [i for i in range(capacity) if i not in self.seats]
            if not free:
                raise RuntimeError("Room is full.")
            preferred_seat = free[0]
        if preferred_seat in self.seats:
            raise ValueError("That seat is taken.")
        seat = Seat(seat=preferred_seat, name=name, token=_token())
        self.seats[preferred_seat] = seat
        return seat

    def start_craft(self, host_token: str) -> None:
        if host_token != self.host_token:
            raise PermissionError("Only the host can start crafting.")
        if self.phase != "lobby":
            raise RuntimeError("Craft already started.")
        need = 1 if self.vs_bot else self.settings.player_count
        if len(self.seats) < need:
            raise RuntimeError(f"Need {need} player(s) (have {len(self.seats)}).")
        self.phase = "craft"
        for seat in self.seats.values():
            seat.deck = []
            seat.ready = False
        self.log = (
            ["Card Lab — craft your deck. Bot builds automatically."]
            if self.vs_bot
            else ["Card Lab — craft your deck."]
        )

    def craft_next(
        self,
        token: str,
        *,
        damage: int,
        steals: bool = False,
        heavy_hit: bool = False,
        shields: bool = False,
        poisons: bool = False,
        exordia: bool = False,
        cloak: bool = False,
        lava: bool = False,
        joker: bool = False,
        reaper: bool = False,
        vampire: bool = False,
        cure: bool = False,
    ) -> Card:
        if self.phase != "craft":
            raise RuntimeError("Not in craft phase.")
        seat = self.seat_by_token(token)
        if seat is None:
            raise PermissionError("Unknown player.")
        if seat.ready:
            raise RuntimeError("You already finished crafting.")
        if steals and self.vs_bot:
            raise ValueError("Steal is disabled in vs-bot mode.")
        need = self.settings.deck_size - 1  # last is Mercy
        if len(seat.deck) >= need:
            raise RuntimeError("All craftable cards are done — finish with Mercy.")
        card = craft_card(
            len(seat.deck) + 1,
            damage,
            self.settings.power_points,
            seat.deck,
            steals=steals,
            heavy_hit=heavy_hit,
            shields=shields,
            poisons=poisons,
            exordia=exordia,
            cloak=cloak,
            lava=lava,
            joker=joker,
            reaper=reaper,
            vampire=vampire,
            cure=cure,
            deck_size=self.settings.deck_size,
        )
        seat.deck.append(card)
        # Vs bot: finishing the last craftable card adds Mercy and starts the match.
        if self.vs_bot and len(seat.deck) >= need:
            if len(seat.deck) == need:
                seat.deck.append(make_mercy_card(self.settings.deck_size, seat.deck))
            seat.ready = True
            self._begin_play()
        return card

    def finish_craft(self, token: str) -> None:
        if self.phase != "craft":
            raise RuntimeError("Not in craft phase.")
        seat = self.seat_by_token(token)
        if seat is None:
            raise PermissionError("Unknown player.")
        need = self.settings.deck_size - 1
        if len(seat.deck) < need:
            raise RuntimeError(f"Craft {need - len(seat.deck)} more card(s) first.")
        if len(seat.deck) == need:
            seat.deck.append(make_mercy_card(self.settings.deck_size, seat.deck))
        seat.ready = True
        if self.vs_bot or all(s.ready for s in self.seats.values()):
            self._begin_play()

    def _begin_play(self) -> None:
        if self.vs_bot:
            human = self.seats[0]
            bot_deck = make_bot_deck(self.settings.power_points, self.settings.deck_size)
            self.players = make_solo_players(
                human.deck, bot_deck, self.settings.starting_hp
            )
            self.players[0].name = human.name
            # ensure bot name stays BOT_NAME
            self.players[1].name = BOT_NAME
        else:
            ordered = [self.seats[i] for i in range(self.settings.player_count)]
            decks = [copy.deepcopy(s.deck) for s in ordered]
            self.players = make_players_from_mixed_decks(
                decks, self.settings.starting_hp
            )
            for i, seat in enumerate(ordered):
                self.players[i].name = seat.name
        self.active = 0
        self.borrows = []
        self.pending_card_id = None
        self.phase = "play"
        self.winner_name = None
        self.log = [f"Match start — {self.players[0].name}'s turn."]
        self._turn_start_ticks()

    def _turn_start_ticks(self) -> None:
        while self.players and self.phase == "play":
            for line in tick_reaper_marks(self.players):
                self.log.append(line)
            winner = check_winner(self.players)
            if winner is not None:
                self.phase = "game_over"
                self.winner_name = winner.name
                self.log.append(f"{winner.name} wins!")
                return

            player = self.players[self.active]
            if not player.alive:
                nxt = next_alive_index(self.players, self.active)
                if nxt is None:
                    self.phase = "game_over"
                    self.log.append("No living players left.")
                    return
                self.active = nxt
                continue

            for line in tick_poisons_on_turn_start(player, self.players):
                self.log.append(line)
            winner = check_winner(self.players)
            if winner is not None:
                self.phase = "game_over"
                self.winner_name = winner.name
                self.log.append(f"{winner.name} wins!")
                return
            if not player.alive:
                nxt = next_alive_index(self.players, self.active)
                if nxt is None:
                    self.phase = "game_over"
                    self.log.append("No living players left.")
                    return
                self.active = nxt
                continue
            return

    def play_card(self, token: str, card_id: int) -> None:
        if self.phase != "play":
            raise RuntimeError("Not in play phase.")
        seat = self.seat_by_token(token)
        if seat is None:
            raise PermissionError("Unknown player.")
        if seat.seat != self.active:
            raise RuntimeError("Not your turn.")
        player = self.players[self.active]
        card = next((c for c in player.hand if c.id == card_id), None)
        if card is None:
            raise ValueError("Card not in your hand.")
        if card_is_cooling(player, card):
            raise RuntimeError("That card is cooling down.")
        self.pending_card_id = card_id

    def _valid_target_indices(self, card: Card) -> list[int]:
        if card.heal_any:
            return [i for i, player in enumerate(self.players) if player.alive]
        if card.exordia and not card.exordia_charged:
            return [self.active]
        if not (
            card.damage > 0
            or card.steals
            or card.heavy_hit
            or card.poisons
            or card.exordia
            or card.lava
            or card.joker
            or card.reaper
            or card.vampire
        ):
            return [self.active]
        opponents = [
            i
            for i, player in enumerate(self.players)
            if i != self.active and player.alive
        ]
        return opponents or [self.active]

    def choose_target(self, token: str, target_idx: int) -> None:
        if self.phase != "play":
            raise RuntimeError("Not in play phase.")
        seat = self.seat_by_token(token)
        if seat is None:
            raise PermissionError("Unknown player.")
        if seat.seat != self.active:
            raise RuntimeError("Not your turn.")
        if self.pending_card_id is None:
            raise RuntimeError("Pick a card first.")
        if not (0 <= target_idx < len(self.players)):
            raise ValueError("Invalid target.")
        target = self.players[target_idx]
        if not target.alive:
            raise ValueError("That player is out.")
        player = self.players[self.active]
        card = next((c for c in player.hand if c.id == self.pending_card_id), None)
        if card is None:
            self.pending_card_id = None
            raise ValueError("Card no longer in hand.")
        if target_idx not in self._valid_target_indices(card):
            raise ValueError("That card cannot target this player.")
        self.pending_card_id = None
        self._execute_play(card, target_idx)

    def _execute_play(self, card: Card, target_idx: int) -> None:
        player = self.players[self.active]
        target = self.players[target_idx]
        self.log.append(f"{player.name} plays {card.name} → {target.name}")
        logs = resolve_card(
            card, self.players, self.active, target_idx, self.borrows
        )
        self.log.extend(logs)
        steal_logs = resolve_steal(
            card, self.players, self.active, target_idx, self.borrows
        )
        self.log.extend(steal_logs)
        mark_card_played(player, card)

        winner = check_winner(self.players)
        if winner is not None:
            self.phase = "game_over"
            self.winner_name = winner.name
            self.pending_card_id = None
            self.log.append(f"{winner.name} wins!")
            return

        return_logs = return_expired_borrows(self.players, self.active, self.borrows)
        self.log.extend(return_logs)
        cd_logs = tick_turn_cooldowns(self.players, self.active)
        self.log.extend(cd_logs)

        nxt = next_alive_index(self.players, self.active)
        if nxt is None:
            self.phase = "game_over"
            self.winner_name = None
            self.log.append("No living players left.")
            self.pending_card_id = None
            return
        self.active = nxt
        self.pending_card_id = None
        self.log.append(f"Turn — {self.players[self.active].name}")
        self._turn_start_ticks()

    def bot_should_act(self) -> bool:
        return (
            self.phase == "play"
            and bool(self.players)
            and self.players[self.active].is_bot
        )

    def run_one_bot_turn(self) -> None:
        """Resolve one bot turn (no-op if it is not the bot's turn)."""
        if not self.bot_should_act():
            return
        choice = bot_choose_play(
            self.players, self.active, self.settings.starting_hp
        )
        if choice is None:
            self.log.append(f"{BOT_NAME} has no playable cards — skipping turn.")
            nxt = next_alive_index(self.players, self.active)
            if nxt is None:
                self.phase = "game_over"
                return
            self.active = nxt
            self.log.append(f"Turn — {self.players[self.active].name}")
            self._turn_start_ticks()
            return
        card, target_idx, reason = choice
        self.log.append(f"{BOT_NAME} thinks: {reason}")
        self._execute_play(card, target_idx)

    def cancel_pending(self, token: str) -> None:
        seat = self.seat_by_token(token)
        if seat is None:
            raise PermissionError("Unknown player.")
        if seat.seat != self.active:
            raise RuntimeError("Not your turn.")
        self.pending_card_id = None

    def view_for(self, token: str | None) -> dict[str, Any]:
        seat = self.seat_by_token(token) if token else None
        settings = self.settings
        seat_rows: list[dict[str, Any]] = []
        if self.vs_bot:
            human = self.seats.get(0)
            seat_rows.append(
                {
                    "seat": 0,
                    "name": human.name if human else None,
                    "ready": human.ready if human else False,
                    "crafted": len(human.deck) if human else 0,
                    "filled": human is not None,
                }
            )
            seat_rows.append(
                {
                    "seat": 1,
                    "name": BOT_NAME,
                    "ready": True,
                    "crafted": settings.deck_size if self.phase != "lobby" else 0,
                    "filled": True,
                    "is_bot": True,
                }
            )
        else:
            for i in range(settings.player_count):
                seat_rows.append(
                    {
                        "seat": i,
                        "name": self.seats[i].name if i in self.seats else None,
                        "ready": self.seats[i].ready if i in self.seats else False,
                        "crafted": len(self.seats[i].deck) if i in self.seats else 0,
                        "filled": i in self.seats,
                    }
                )
        payload: dict[str, Any] = {
            "code": self.code,
            "phase": self.phase,
            "is_host": bool(token and token == self.host_token),
            "your_seat": seat.seat if seat else None,
            "vs_bot": self.vs_bot,
            "settings": {
                "player_count": settings.player_count,
                "starting_hp": settings.starting_hp,
                "power_points": settings.power_points,
                "deck_size": settings.deck_size,
                "allow_duplicates": allows_duplicate_archetypes(settings.deck_size),
                "mercy_heal": FIFTH_CARD_HEAL,
                "vs_bot": self.vs_bot,
            },
            "seats": seat_rows,
            "log": self.log[-40:],
            "winner": self.winner_name,
            "active": self.active if self.phase in ("play", "game_over") else None,
            "pending_card_id": self.pending_card_id
            if seat and seat.seat == self.active
            else None,
            "players": [],
            "your_hand": [],
            "your_deck": [],
            "craft": None,
        }

        if self.phase in ("play", "game_over"):
            for i, p in enumerate(self.players):
                payload["players"].append(
                    {
                        "seat": i,
                        "name": p.name,
                        "hp": p.hp,
                        "max_hp": p.max_hp,
                        "alive": p.alive,
                        "shield": p.shield_charges > 0,
                        "poisoned": p.poisoned,
                        "reaper_marked": bool(p.reaper_marks),
                        "vampire_marked": bool(p.vampire_marks),
                        "cloak_charges": p.cloak_charges,
                        "hand_count": len(p.hand),
                        "is_active": i == self.active,
                        "is_bot": p.is_bot,
                    }
                )
            if seat is not None and seat.seat < len(self.players):
                me = self.players[seat.seat]
                payload["your_hand"] = [
                    _public_card(c, cooling=card_is_cooling(me, c)) for c in me.hand
                ]
                if (
                    self.pending_card_id is not None
                    and seat.seat == self.active
                ):
                    pending = next(
                        (c for c in me.hand if c.id == self.pending_card_id), None
                    )
                    payload["pending_targets"] = (
                        self._valid_target_indices(pending) if pending is not None else []
                    )

        if self.phase == "craft" and seat is not None:
            need = settings.deck_size - 1
            crafted = len(seat.deck)
            pp = settings.power_points
            can_add_unique = (
                settings.deck_size != DECK_SIZE
                or unique_card_total(seat.deck) < MAX_UNIQUE_CARDS_IN_DECK
            )
            payload["your_deck"] = [_public_card(c) for c in seat.deck]
            payload["craft"] = {
                "slot": min(crafted + 1, settings.deck_size),
                "need_craftable": need,
                "crafted": crafted,
                "ready": seat.ready,
                "done_craftable": crafted >= need,
                "budget_full": pp,
                "can_steal": (
                    can_add_unique
                    and (not self.vs_bot)
                    and can_add_steal_card(seat.deck, pp)
                ),
                "can_heavy": can_add_unique and can_add_heavy_hit_card(seat.deck),
                "can_shield": (
                    can_add_unique and can_add_shield_card(seat.deck, pp)
                ),
                "can_poison": can_add_unique and can_add_poison_card(seat.deck),
                "can_exordia": can_add_unique
                and not any(c.exordia for c in seat.deck),
                "can_cloak": can_add_unique and not any(c.cloak for c in seat.deck),
                "can_lava": can_add_unique and not any(c.lava for c in seat.deck),
                "can_joker": can_add_unique and not any(c.joker for c in seat.deck),
                "can_reaper": can_add_unique and not any(c.reaper for c in seat.deck),
                "can_vampire": can_add_unique and can_add_vampire_card(seat.deck),
                "can_cure": can_add_unique and not any(c.cure for c in seat.deck),
                "budget_steal": stat_budget(pp, True),
                "budget_shield": stat_budget(pp, shields=True),
            }
        return payload
