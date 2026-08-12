#!/usr/bin/env python3
"""Shared Crash Out game rules (used by terminal and window UIs)."""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

DEFAULT_STARTING_HP = 100
DEFAULT_POWER_POINTS = 50
PLAYER_COUNT_MIN = 1
PLAYER_COUNT_MAX = 4
DECK_SIZE = 5
FIFTH_CARD_HEAL = 25
STEAL_PP_COST = 25
HEAVY_HIT_MULTIPLIER = 1.5
COOLDOWN_CLEAR_TURNS = 2
BORROW_TURNS = 2  # return after thief ends this many turns (steal turn + 1 more)
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
    steals: bool = False
    heavy_hit: bool = False
    borrowed_from: int | None = None

    @property
    def effect(self) -> str:
        if self.heal_any:
            return f"Heal any target for {self.heal} HP (you also heal if target isn't you)."
        dmg, heal = effective_card_stats(self)
        base = f"{dmg} dmg to target / {heal} heal to you"
        if self.steals:
            return base + " / steal 1 opponent card for 1 turn"
        if self.heavy_hit:
            return base + f" / clears target cooldowns for {COOLDOWN_CLEAR_TURNS} turns"
        return base

    def label(self) -> str:
        if self.heal_any:
            base = f"{self.name} — heal {self.heal} HP (any target)"
        else:
            primary, extra = self.face_stats()
            primary_line = primary.replace("\n", " ")
            extra_note = ""
            if self.steals:
                extra_note = " + steal"
            elif self.heavy_hit:
                extra_note = " + Heavy Hit"
            if not extra:
                base = f"{self.name} — {primary_line}{extra_note}"
            else:
                base = f"{self.name} — {primary_line} / {extra}"
        if self.is_borrowed:
            return base + " (borrowed)"
        return base

    @property
    def is_borrowed(self) -> bool:
        return self.borrowed_from is not None

    def face_stats(self) -> tuple[str, str]:
        """
        Primary stat (large) and extra detail (small) for card faces.
        Extra is heal when heal <= damage, otherwise damage.
        """
        if self.heal_any:
            return f"HEAL\n{self.heal}", "any target"
        dmg, heal = effective_card_stats(self)
        if heal <= dmg:
            primary = f"{dmg}\nDMG"
            extra = f"+{heal} heal you" if heal > 0 else ""
        else:
            primary = f"{heal}\nHEAL"
            extra = f"+{dmg} dmg to target" if dmg > 0 else ""
        if self.steals:
            steal_line = "steal 1 card"
            extra = f"{extra} / {steal_line}" if extra else steal_line
        elif self.heavy_hit:
            heavy_line = "clear cd 2t"
            extra = f"{extra} / {heavy_line}" if extra else heavy_line
        return primary, extra


@dataclass
class ActiveBorrow:
    card: Card
    owner_idx: int
    thief_idx: int
    turns_left: int = BORROW_TURNS


@dataclass
class Player:
    name: str
    hp: int
    max_hp: int
    hand: list[Card] = field(default_factory=list)
    last_card_id: int | None = None
    cooldown_clear_turns: int = 0

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def is_bot(self) -> bool:
        return self.name == BOT_NAME

    def playable_cards(self) -> list[Card]:
        if self.cooldown_clear_turns > 0:
            return list(self.hand)
        return [c for c in self.hand if c.id != self.last_card_id]


def card_is_cooling(player: Player, card: Card) -> bool:
    return player.cooldown_clear_turns <= 0 and card.id == player.last_card_id


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


def card_archetype(card: Card) -> str:
    """Sanctuary / Caretaker / Allrounder / Bruiser / Wrecker / Mercy / Heavy Hit."""
    if card.heal_any:
        return "Mercy"
    if card.heavy_hit:
        return "Heavy Hit"
    return name_for_split(card.damage, card.heal, card.damage + card.heal)


def archetype_taken(archetype: str, existing: list[Card]) -> bool:
    return any(card_archetype(c) == archetype for c in existing)


def stat_budget(power_points: int, steals: bool) -> int:
    if steals:
        return power_points - STEAL_PP_COST
    return power_points


def can_craft_steal(power_points: int) -> bool:
    return power_points >= STEAL_PP_COST


def deck_has_steal(existing: list[Card]) -> bool:
    return any(c.steals for c in existing)


def can_add_steal_card(existing: list[Card], power_points: int) -> bool:
    return can_craft_steal(power_points) and not deck_has_steal(existing)


def deck_has_heavy_hit(existing: list[Card]) -> bool:
    return any(c.heavy_hit for c in existing)


def can_add_heavy_hit_card(existing: list[Card]) -> bool:
    return not deck_has_heavy_hit(existing)


def effective_card_stats(card: Card) -> tuple[int, int]:
    if card.heavy_hit:
        return (
            int(round(card.damage * HEAVY_HIT_MULTIPLIER)),
            int(round(card.heal * HEAVY_HIT_MULTIPLIER)),
        )
    return card.damage, card.heal


def craft_card(
    card_id: int,
    damage: int,
    power_points: int,
    existing: list[Card],
    *,
    steals: bool = False,
    heavy_hit: bool = False,
) -> Card:
    """
    Build a craftable card. Raises ValueError if that archetype is already
    in the deck (no duplicate types allowed).
    """
    if steals and heavy_hit:
        raise ValueError("A card cannot have both steal and Heavy Hit.")
    if steals and not can_craft_steal(power_points):
        raise ValueError(f"Steal costs {STEAL_PP_COST} PP — not enough budget.")
    if steals and deck_has_steal(existing):
        raise ValueError("Your deck already has a steal card. Only one per deck.")
    if heavy_hit and deck_has_heavy_hit(existing):
        raise ValueError("Your deck already has a Heavy Hit card. Only one per deck.")
    budget = stat_budget(power_points, steals)
    damage = max(0, min(budget, damage))
    heal = budget - damage
    base = "Heavy Hit" if heavy_hit else name_for_split(damage, heal, budget)
    if archetype_taken(base, existing):
        raise ValueError(
            f"Your deck already has a {base} card. "
            "Pick a different damage/heal split."
        )
    return Card(
        id=card_id,
        name=base,
        damage=damage,
        heal=heal,
        heal_any=False,
        steals=steals,
        heavy_hit=heavy_hit,
    )


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


def normalize_hand_ids(hand: list[Card]) -> list[Card]:
    """Assign ids 1..n for cooldown tracking on a dealt hand."""
    normalized: list[Card] = []
    for i, card in enumerate(hand, start=1):
        dealt = copy.deepcopy(card)
        dealt.id = i
        dealt.borrowed_from = None
        normalized.append(dealt)
    return normalized


def is_protected_card(card: Card) -> bool:
    """Mercy, steal, and Heavy Hit cards stay with the player who crafted them."""
    return card.heal_any or card.steals or card.heavy_hit


def shuffle_and_deal_hands(player_decks: list[list[Card]]) -> list[list[Card]]:
    """Shuffle craftable cards only; Mercy and steal cards stay with their owner."""
    if not player_decks:
        return []
    n = len(player_decks)
    protected_hands: list[list[Card]] = []
    shuffle_pool: list[Card] = []

    for deck in player_decks:
        protected = [copy.deepcopy(c) for c in deck if is_protected_card(c)]
        shuffleable = [copy.deepcopy(c) for c in deck if not is_protected_card(c)]
        protected_hands.append(protected)
        shuffle_pool.extend(shuffleable)

    quotas = [DECK_SIZE - len(protected) for protected in protected_hands]
    if sum(quotas) != len(shuffle_pool):
        raise ValueError(
            f"Shuffle pool size {len(shuffle_pool)} does not match deal quotas {quotas}."
        )

    random.shuffle(shuffle_pool)
    hands: list[list[Card]] = []
    offset = 0
    for protected, quota in zip(protected_hands, quotas):
        drawn = shuffle_pool[offset : offset + quota]
        offset += quota
        hands.append(normalize_hand_ids(protected + drawn))
    return hands


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


def make_players_from_mixed_decks(
    player_decks: list[list[Card]],
    starting_hp: int,
) -> list[Player]:
    """Combine crafted decks, shuffle, and deal hands for hotseat multiplayer."""
    hands = shuffle_and_deal_hands(player_decks)
    max_hp = starting_hp * 2
    return [
        Player(
            name=f"player-{i + 1}",
            hp=starting_hp,
            max_hp=max_hp,
            hand=hands[i],
        )
        for i in range(len(hands))
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
    damage, heal = effective_card_stats(card)

    if card.heal_any:
        logs.extend(apply_heal(target, card.heal))
        if target_idx != active and card.heal > 0:
            logs.append("(Mercy also restores the caster.)")
            logs.extend(apply_heal(caster, card.heal))
        return logs

    if target_idx == active:
        if heal > 0:
            logs.extend(apply_heal(caster, heal))
        else:
            logs.append(f"{card.name} has 0 heal — nothing happens on self.")
        if damage > 0:
            logs.append(f"(Its {damage} damage is ignored on self.)")
        if card.heavy_hit:
            logs.extend(apply_heavy_hit_cooldown_effect(target))
        return logs

    if damage > 0:
        logs.extend(apply_damage(target, damage))
    else:
        logs.append(f"{card.name} has 0 damage — no damage to {target.name}.")
    if heal > 0:
        logs.extend(apply_heal(caster, heal))
    elif damage > 0:
        logs.append("(This card has 0 heal — caster gains nothing.)")
    if card.heavy_hit:
        logs.extend(apply_heavy_hit_cooldown_effect(target))
    return logs


def apply_heavy_hit_cooldown_effect(target: Player) -> list[str]:
    target.last_card_id = None
    target.cooldown_clear_turns = COOLDOWN_CLEAR_TURNS
    return [
        f"{target.name}'s cooldowns are cleared for {COOLDOWN_CLEAR_TURNS} turns "
        "(Heavy Hit)."
    ]


def tick_turn_cooldowns(players: list[Player], ending_idx: int) -> list[str]:
    logs: list[str] = []
    player = players[ending_idx]
    if player.cooldown_clear_turns > 0:
        player.cooldown_clear_turns -= 1
        if player.cooldown_clear_turns <= 0:
            player.cooldown_clear_turns = 0
            logs.append(f"{player.name}'s Heavy Hit cooldown relief ended.")
    return logs


def steal_applies(
    card: Card,
    players: list[Player],
    active: int,
    target_idx: int,
) -> bool:
    if not card.steals or target_idx == active:
        return False
    if players[active].is_bot or players[target_idx].is_bot:
        return False
    return True


def random_steal_index(hand: list[Card]) -> int:
    if not hand:
        return 0
    return random.randrange(len(hand))


def resolve_steal(
    card: Card,
    players: list[Player],
    active: int,
    target_idx: int,
    borrows: list[ActiveBorrow],
) -> list[str]:
    if not steal_applies(card, players, active, target_idx):
        return []
    victim = players[target_idx]
    if not victim.hand:
        return [f"{victim.name} has no cards to steal."]
    steal_idx = random_steal_index(victim.hand)
    return apply_steal(players, active, target_idx, steal_idx, borrows)


def apply_steal(
    players: list[Player],
    thief_idx: int,
    victim_idx: int,
    hand_index: int,
    borrows: list[ActiveBorrow],
) -> list[str]:
    logs: list[str] = []
    thief = players[thief_idx]
    victim = players[victim_idx]
    if not victim.hand:
        logs.append(f"{victim.name} has no cards to steal.")
        return logs
    hand_index = max(0, min(len(victim.hand) - 1, hand_index))
    stolen = victim.hand.pop(hand_index)
    stolen.borrowed_from = victim_idx
    thief.hand.append(stolen)
    borrows.append(
        ActiveBorrow(
            card=stolen,
            owner_idx=victim_idx,
            thief_idx=thief_idx,
        )
    )
    logs.append(
        f"{thief.name} steals {stolen.name} from {victim.name} "
        f"(returns after {BORROW_TURNS - 1} more of {thief.name}'s turns)"
    )
    return logs


def return_expired_borrows(
    players: list[Player],
    ending_player_idx: int,
    borrows: list[ActiveBorrow],
) -> tuple[list[ActiveBorrow], list[str]]:
    logs: list[str] = []
    still_active: list[ActiveBorrow] = []
    for borrow in borrows:
        if borrow.thief_idx != ending_player_idx:
            still_active.append(borrow)
            continue
        borrow.turns_left -= 1
        if borrow.turns_left <= 0:
            thief = players[borrow.thief_idx]
            owner = players[borrow.owner_idx]
            if borrow.card in thief.hand:
                thief.hand.remove(borrow.card)
            borrow.card.borrowed_from = None
            owner.hand.append(borrow.card)
            logs.append(f"{borrow.card.name} returns to {owner.name}'s hand.")
        else:
            still_active.append(borrow)
    return still_active, logs


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
    if card.steals:
        return who + " (damage them + heal you + steal 1 card)"
    if card.heavy_hit:
        if target_idx == active:
            return who + " (self — +50% heal, clears your cooldowns 2 turns)"
        return who + " (damage them + heal you +50%, clears their cooldowns 2 turns)"
    return who + " (damage them + heal you)"
