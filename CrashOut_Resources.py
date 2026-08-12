#!/usr/bin/env python3
"""Shared Crash Out game rules (used by terminal and window UIs)."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

DEFAULT_STARTING_HP = 100
DEFAULT_POWER_POINTS = 50
PLAYER_COUNT_MIN = 1
PLAYER_COUNT_MAX = 4
DECK_SIZE = 5
FIFTH_CARD_HEAL = 25
BOT_NAME = "bot"
HP_MIN, HP_MAX = 1, 9999
PP_MIN, PP_MAX = 1, 999
TURN_DELAY_MS = 500
TURN_DELAY_SEC = 0.5


@dataclass
class Card:
    id: int
    name: str
    damage: int
    heal: int
    heal_any: bool = False

    @property
    def effect(self) -> str:
        if self.heal_any:
            return f"Heal any target for {self.heal} HP (you also heal if target isn't you)."
        return f"{self.damage} dmg to target / {self.heal} heal to you"

    def label(self) -> str:
        if self.heal_any:
            return f"{self.name} — heal {self.heal} HP (any target)"
        return f"{self.name} — {self.damage} dmg to target / {self.heal} heal to you"


@dataclass
class Player:
    name: str
    hp: int
    max_hp: int
    hand: list[Card] = field(default_factory=list)
    last_card_id: int | None = None

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def is_bot(self) -> bool:
        return self.name == BOT_NAME

    def playable_cards(self) -> list[Card]:
        return [c for c in self.hand if c.id != self.last_card_id]


@dataclass
class MatchSettings:
    player_count: int
    starting_hp: int
    power_points: int

    @property
    def vs_bot(self) -> bool:
        return self.player_count == 1

    @property
    def max_hp(self) -> int:
        return self.starting_hp * 2


def name_for_split(damage: int, heal: int, power_points: int) -> str:
    if damage == heal:
        return "Allrounder"
    if power_points <= 0:
        return "Allrounder"
    ratio = damage / power_points
    bucket = int(round(ratio * 4))
    bucket = max(0, min(4, bucket))
    names = {
        0: "Sanctuary",
        1: "Caretaker",
        2: "Allrounder",
        3: "Bruiser",
        4: "Wrecker",
    }
    return names[bucket]


def damage_for_bucket(bucket: int, power_points: int) -> int:
    if bucket <= 0:
        return 0
    if bucket >= 4:
        return power_points
    return int(round(power_points * bucket / 4))


def uniquify_name(base: str, existing: list[Card]) -> str:
    used = {c.name for c in existing}
    if base not in used:
        return base
    n = 2
    while f"{base} {n}" in used:
        n += 1
    return f"{base} {n}"


def craft_card(
    card_id: int,
    damage: int,
    power_points: int,
    existing: list[Card],
) -> Card:
    damage = max(0, min(power_points, damage))
    heal = power_points - damage
    base = name_for_split(damage, heal, power_points)
    name = uniquify_name(base, existing)
    return Card(id=card_id, name=name, damage=damage, heal=heal, heal_any=False)


def make_mercy_card(card_id: int = DECK_SIZE, existing: list[Card] | None = None) -> Card:
    name = "Mercy"
    if existing is not None:
        name = uniquify_name("Mercy", existing)
    return Card(
        id=card_id,
        name=name,
        damage=0,
        heal=FIFTH_CARD_HEAL,
        heal_any=True,
    )


def make_bot_deck(power_points: int) -> list[Card]:
    specs = [
        (1, "Caretaker", 1),
        (2, "Bruiser", 3),
        (3, "Wrecker", 4),
        (4, "Sanctuary", 0),
    ]
    deck: list[Card] = []
    for card_id, name, bucket in specs:
        damage = damage_for_bucket(bucket, power_points)
        heal = power_points - damage
        deck.append(
            Card(id=card_id, name=name, damage=damage, heal=heal, heal_any=False)
        )
    deck.append(make_mercy_card(DECK_SIZE))
    return deck


def make_players(count: int, deck: list[Card], starting_hp: int) -> list[Player]:
    max_hp = starting_hp * 2
    return [
        Player(
            name=f"player-{i}",
            hp=starting_hp,
            max_hp=max_hp,
            hand=copy.deepcopy(deck),
        )
        for i in range(1, count + 1)
    ]


def make_solo_players(
    human_deck: list[Card],
    bot_deck: list[Card],
    starting_hp: int,
) -> list[Player]:
    max_hp = starting_hp * 2
    return [
        Player(
            name="player-1",
            hp=starting_hp,
            max_hp=max_hp,
            hand=copy.deepcopy(human_deck),
        ),
        Player(
            name=BOT_NAME,
            hp=starting_hp,
            max_hp=max_hp,
            hand=copy.deepcopy(bot_deck),
        ),
    ]


def apply_damage(target: Player, damage: int) -> list[str]:
    target.hp = max(0, target.hp - damage)
    if target.hp == 0:
        return [f"{target.name} takes {damage} damage and is OUT!"]
    return [
        f"{target.name} takes {damage} damage ({target.hp}/{target.max_hp} HP left)"
    ]


def apply_heal(target: Player, amount: int) -> list[str]:
    before = target.hp
    target.hp = min(target.max_hp, target.hp + amount)
    gained = target.hp - before
    if gained < amount:
        return [
            f"{target.name} heals {gained} HP "
            f"(capped at max {target.max_hp}; now {target.hp}/{target.max_hp})"
        ]
    return [f"{target.name} heals {gained} HP ({target.hp}/{target.max_hp} HP now)"]


def resolve_card(
    card: Card,
    players: list[Player],
    active: int,
    target_idx: int,
) -> list[str]:
    """
    Normal cards:
      - Target other: damage them, then heal the caster.
      - Target self: heal the caster only (no self-damage).
    Mercy: heal the target; if that isn't you, you also heal.
    """
    logs: list[str] = []
    caster = players[active]
    target = players[target_idx]

    if card.heal_any:
        logs.extend(apply_heal(target, card.heal))
        if target_idx != active and card.heal > 0:
            logs.append("(Mercy also restores the caster.)")
            logs.extend(apply_heal(caster, card.heal))
        return logs

    if target_idx == active:
        if card.heal > 0:
            logs.extend(apply_heal(caster, card.heal))
        else:
            logs.append(f"{card.name} has 0 heal — nothing happens on self.")
        if card.damage > 0:
            logs.append(f"(Its {card.damage} damage is ignored on self.)")
        return logs

    if card.damage > 0:
        logs.extend(apply_damage(target, card.damage))
    else:
        logs.append(f"{card.name} has 0 damage — no damage to {target.name}.")
    if card.heal > 0:
        logs.extend(apply_heal(caster, card.heal))
    elif card.damage > 0:
        logs.append("(This card has 0 heal — caster gains nothing.)")
    return logs


def check_winner(players: list[Player]) -> Player | None:
    alive = [p for p in players if p.alive]
    if len(alive) == 1:
        return alive[0]
    return None


def next_alive_index(players: list[Player], current: int) -> int | None:
    n = len(players)
    for step in range(1, n + 1):
        i = (current + step) % n
        if players[i].alive:
            return i
    return None


def first_living_opponent(players: list[Player], active: int) -> int | None:
    for i, p in enumerate(players):
        if i != active and p.alive:
            return i
    return None


def bot_choose_play(
    players: list[Player],
    active: int,
    starting_hp: int,
) -> tuple[Card, int, str] | None:
    bot = players[active]
    playable = bot.playable_cards()
    if not playable:
        return None

    foe = first_living_opponent(players, active)
    if foe is None:
        return playable[0], active, "no opponents left"

    foe_hp = players[foe].hp
    half = max(1, starting_hp // 2)
    wants_heal = bot.hp <= half

    lethal = [c for c in playable if not c.heal_any and c.damage >= foe_hp]
    if lethal:
        card = max(lethal, key=lambda c: c.damage)
        return (
            card,
            foe,
            f"bot at {bot.hp} HP — finishing blow ({card.damage} >= {foe_hp})",
        )

    healers = [c for c in playable if c.heal > 0 or c.heal_any]
    attackers = [c for c in playable if not c.heal_any and c.damage > 0]

    if wants_heal and healers:
        card = max(healers, key=lambda c: c.heal)
        return card, active, f"bot at {bot.hp} HP (<= {half}) — healing"

    if attackers:
        card = max(attackers, key=lambda c: c.damage)
        reason = (
            f"bot at {bot.hp} HP (> {half}) — attacking"
            if not wants_heal
            else f"bot at {bot.hp} HP — no heal card ready, attacking"
        )
        return card, foe, reason

    card = max(playable, key=lambda c: c.heal)
    return card, active, f"bot at {bot.hp} HP — healing with {card.name}"


def describe_target(
    card: Card,
    players: list[Player],
    active: int,
    target_idx: int,
) -> str:
    who = players[target_idx].name
    if card.heal_any:
        if target_idx == active:
            return who + " (heal self)"
        return who + " (heal them + heal you)"
    if target_idx == active:
        return who + " (self — heal yourself)"
    return who + " (damage them + heal you)"
