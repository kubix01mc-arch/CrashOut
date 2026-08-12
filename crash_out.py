#!/usr/bin/env python3
"""Crash Out — terminal hotseat UI."""

from __future__ import annotations

import os
import sys
import time

from CrashOut_Resources import (
    BOT_NAME,
    DEFAULT_POWER_POINTS,
    DEFAULT_STARTING_HP,
    DECK_SIZE,
    FIFTH_CARD_HEAL,
    HP_MAX,
    HP_MIN,
    MatchSettings,
    PLAYER_COUNT_MIN,
    PP_MAX,
    PP_MIN,
    TURN_DELAY_SEC,
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


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause(msg: str = "Press Enter to continue...") -> None:
    input(msg)


def turn_delay(msg: str | None = None) -> None:
    if msg:
        print(msg)
    time.sleep(TURN_DELAY_SEC)


def prompt(msg: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{msg}{suffix}: ").strip()
        if raw:
            return raw
        if default is not None:
            return default
        print("  Please enter something.")


def prompt_int(msg: str, lo: int, hi: int, default: int | None = None) -> int:
    suffix = f" [{default}]" if default is not None else f" ({lo}-{hi})"
    range_hint = f" ({lo}-{hi})" if default is not None else ""
    while True:
        raw = input(f"{msg}{range_hint}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            n = int(raw)
            if lo <= n <= hi:
                return n
        except ValueError:
            pass
        print(f"  Enter a number between {lo} and {hi}.")


def prompt_choice(msg: str, options: list[str]) -> int:
    print(msg)
    for i, opt in enumerate(options, start=1):
        print(f"  {i}) {opt}")
    return prompt_int("Choice", 1, len(options)) - 1


def banner(title: str) -> None:
    line = "=" * 52
    print(f"\n{line}\n  CRASH OUT — {title}\n{line}\n")


def print_card(card: Card, index: int | None = None, cooling_down: bool = False) -> None:
    prefix = f"  [{index}] " if index is not None else "  "
    line = f"{prefix}{card.label()}"
    if cooling_down:
        line += "  (cooling down — can't use this turn)"
    print(line)


def print_status(players: list[Player], active: int | None = None) -> None:
    print("Players:")
    for i, p in enumerate(players):
        mark = " <--" if i == active else ""
        status = f"{p.hp}/{p.max_hp} HP" if p.alive else "OUT"
        print(f"  {i + 1}. {p.name}: {status}{mark}")
    print()


def create_card(
    card_id: int,
    slot: int,
    power_points: int,
    existing: list[Card],
) -> Card:
    clear()
    banner(f"Create Card {slot}/{DECK_SIZE}")
    print(f"Spend exactly {power_points} power points.")
    print("Each point becomes either 1 damage or 1 heal.")
    print("Damage hits the target; heal always returns to YOU.\n")
    print("Name is chosen automatically from the split:")
    print("  Sanctuary / Caretaker / Allrounder / Bruiser / Wrecker\n")

    damage = prompt_int("Damage points", 0, power_points)
    heal = power_points - damage
    print(f"  -> Heal points auto-set to {heal}")
    card = craft_card(card_id, damage, power_points, existing)
    print(f"  -> Auto-named: {card.name}")
    print()
    print_card(card)
    print()
    pause("Card saved — press Enter...")
    return card


def create_fifth_card(existing: list[Card]) -> Card:
    clear()
    banner(f"Create Card {DECK_SIZE}/{DECK_SIZE}")
    print(f"Special heal card — always heals {FIFTH_CARD_HEAL} HP to the target.")
    card = make_mercy_card(DECK_SIZE, existing)
    print(f"\nAuto-named: {card.name}\n")
    print_card(card)
    print()
    pause("Card saved — press Enter...")
    return card


def create_shared_deck(power_points: int, for_solo: bool = False) -> list[Card]:
    clear()
    banner("Card Lab")
    if for_solo:
        print("Build YOUR deck of 5 cards. The bot uses a fixed deck.")
    else:
        print(f"Create a shared deck of {DECK_SIZE} cards.")
    print(f"Cards 1–4: {power_points} power points each.")
    print(f"Card 5: Mercy ({FIFTH_CARD_HEAL} heal, any target).")
    if for_solo:
        print(
            f"\nBot deck: Caretaker, Bruiser, Wrecker, Sanctuary, Mercy "
            f"({power_points} PP)."
        )
    print()
    pause()

    deck: list[Card] = []
    for slot in range(1, DECK_SIZE):
        deck.append(create_card(slot, slot, power_points, deck))
    deck.append(create_fifth_card(deck))

    clear()
    banner("Your Deck Ready" if for_solo else "Shared Deck Ready")
    for i, card in enumerate(deck, start=1):
        print_card(card, i)
    print()
    pause()
    return deck


def choose_match_settings() -> MatchSettings:
    clear()
    banner("Match Setup")
    size_pick = prompt_choice(
        "Pick a match size:",
        ["1 player (vs bot)", "2 players", "3 players", "4 players"],
    )
    player_count = size_pick + PLAYER_COUNT_MIN
    print()
    starting_hp = prompt_int(
        "Starting HP", HP_MIN, HP_MAX, DEFAULT_STARTING_HP
    )
    print()
    power_points = prompt_int(
        "Power points per card", PP_MIN, PP_MAX, DEFAULT_POWER_POINTS
    )
    print()
    print(
        f"  {'1 player vs bot' if player_count == 1 else f'{player_count} players'} | "
        f"{starting_hp} HP (max {starting_hp * 2}) | {power_points} PP"
    )
    pause()
    return MatchSettings(player_count, starting_hp, power_points)


def pass_device(next_player: Player) -> None:
    clear()
    if next_player.is_bot:
        banner("Bot's Turn")
        print("  The bot is about to play.\n")
        turn_delay()
        return
    banner(f"Turn — {next_player.name}")
    print(f"  Starting {next_player.name}'s turn...\n")
    turn_delay()


def choose_target(players: list[Player], active: int, card: Card) -> int | None:
    legal = [i for i, p in enumerate(players) if p.alive]
    if not legal:
        return None
    options = []
    for i in legal:
        label = f"{players[i].name} ({players[i].hp}/{players[i].max_hp} HP)"
        if card.heal_any:
            label += " (heal target; you also heal)"
        elif i == active:
            label += " (you — heal yourself)"
        else:
            label += " (damage them + heal you)"
        options.append(label)
    return legal[prompt_choice("Choose a target:", options)]


def announce_play(player: Player, card: Card) -> None:
    if card.heal_any:
        print(f"\n>>> {player.name} plays '{card.name}' (heal {card.heal})!\n")
    else:
        print(
            f"\n>>> {player.name} plays '{card.name}' "
            f"({card.damage} dmg / {card.heal} heal)!\n"
        )


def play_turn(players: list[Player], active: int, starting_hp: int) -> None:
    player = players[active]
    clear()
    banner(f"Turn — {player.name}")
    print_status(players, active)

    playable = player.playable_cards()
    if not playable:
        print(f"{player.name} has no playable cards — turn skipped.")
        player.last_card_id = None
        turn_delay()
        return

    if player.is_bot:
        print("Bot hand:")
        for i, card in enumerate(player.hand, start=1):
            print_card(card, i, cooling_down=(card.id == player.last_card_id))
        print()
        choice = bot_choose_play(players, active, starting_hp)
        if choice is None:
            print("Bot has no playable cards — turn skipped.")
            player.last_card_id = None
            turn_delay()
            return
        card, target_idx, reason = choice
        player.last_card_id = card.id
        print(f"Bot plan: {reason}\n")
        announce_play(player, card)
        print(f"Targeted: {describe_target(card, players, active, target_idx)}")
        print("\n--- Resolve ---")
        for line in resolve_card(card, players, active, target_idx):
            print(f"  -> {line}")
        print()
        print_status(players)
        turn_delay("Ending bot turn...")
        return

    print("Your cards (reuse allowed; not twice in a row):\n")
    for i, card in enumerate(player.hand, start=1):
        print_card(card, i, cooling_down=(card.id == player.last_card_id))
    print()

    while True:
        pick = prompt_int("Play which card #", 1, len(player.hand)) - 1
        card = player.hand[pick]
        if card.id == player.last_card_id:
            print(f"  '{card.name}' is cooling down — pick a different card.")
            continue
        break
    player.last_card_id = card.id
    announce_play(player, card)

    target_idx = choose_target(players, active, card)
    if target_idx is None:
        print("No valid targets.")
    else:
        print(f"Targeted: {describe_target(card, players, active, target_idx)}")
        print("\n--- Resolve ---")
        for line in resolve_card(card, players, active, target_idx):
            print(f"  -> {line}")

    print()
    print_status(players)
    turn_delay("Ending turn...")


def game_loop(players: list[Player], starting_hp: int) -> None:
    active = 0
    while True:
        if not players[active].alive:
            nxt = next_alive_index(players, active)
            if nxt is None:
                break
            active = nxt
            continue

        pass_device(players[active])
        play_turn(players, active, starting_hp)

        winner = check_winner(players)
        if winner is not None:
            clear()
            banner("Game Over")
            print_status(players)
            print(f"  *** {winner.name} wins! ***\n")
            pause()
            return

        nxt = next_alive_index(players, active)
        if nxt is None:
            clear()
            banner("Game Over")
            print("No one left standing.\n")
            pause()
            return
        active = nxt


def main() -> None:
    try:
        clear()
        banner("Welcome")
        print("Terminal mode — hotseat or 1 player vs bot.")
        print("Attack: damage target + heal you. Self: heal only.")
        print(f"Max HP = 2x starting. Card 5 = Mercy ({FIFTH_CARD_HEAL}).")
        print(f"Bot ({BOT_NAME}): Caretaker, Bruiser, Wrecker, Sanctuary, Mercy.\n")
        pause()

        settings = choose_match_settings()
        human_deck = create_shared_deck(
            settings.power_points, for_solo=settings.vs_bot
        )

        if settings.vs_bot:
            bot_deck = make_bot_deck(settings.power_points)
            players = make_solo_players(
                human_deck, bot_deck, settings.starting_hp
            )
            clear()
            banner("Bot Deck")
            for i, card in enumerate(bot_deck, start=1):
                print_card(card, i)
            print()
            pause()
        else:
            players = make_players(
                settings.player_count, human_deck, settings.starting_hp
            )

        clear()
        banner("Players")
        print_status(players)
        pause("Press Enter to begin...")
        game_loop(players, settings.starting_hp)

        clear()
        banner("Thanks for playing")
        if prompt("Play again? (y/n)", "n").lower().startswith("y"):
            main()
    except KeyboardInterrupt:
        print("\n\nAborted. See you next crash-out.")
        sys.exit(0)


if __name__ == "__main__":
    main()
