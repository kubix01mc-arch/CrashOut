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
    STEAL_PP_COST,
    TURN_DELAY_SEC,
    ActiveBorrow,
    Card,
    Player,
    bot_choose_play,
    card_is_cooling,
    can_add_steal_card,
    check_winner,
    craft_card,
    can_add_heavy_hit_card,
    describe_target,
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
    tick_turn_cooldowns,
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


def prompt_yes_no(msg: str) -> bool:
    while True:
        raw = input(f"{msg} (y/n): ").strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please enter y or n.")


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
    *,
    allow_steal: bool = True,
) -> Card:
    steals = False
    if allow_steal and can_add_steal_card(existing, power_points):
        steals = prompt_yes_no(
            f"Spend {STEAL_PP_COST} PP so this card steals 1 opponent card for 1 turn? "
            "(Only one steal card per deck.)"
        )
    heavy_hit = False
    if not steals and can_add_heavy_hit_card(existing):
        heavy_hit = prompt_yes_no(
            "Add Heavy Hit? (+50% damage/heal, 2-turn cooldown, clears target "
            "cooldowns for 2 turns; one per deck.)"
        )
    budget = stat_budget(power_points, steals)
    while True:
        clear()
        banner(f"Create Card {slot}/{DECK_SIZE}")
        if steals:
            print(
                f"Spend {STEAL_PP_COST} PP on steal + {budget} PP on damage/heal "
                f"({power_points} total)."
            )
        elif heavy_hit:
            print(
                f"Spend {power_points} power points on damage/heal. "
                "Heavy Hit: +50% power, 2-turn cooldown, clears target cooldowns for 2 turns."
            )
        else:
            print(f"Spend exactly {power_points} power points.")
        print("Each point becomes either 1 damage or 1 heal.")
        print("Damage hits the target; heal always returns to YOU.")
        print("You cannot have two cards of the same type in your deck.\n")
        print("Types: Sanctuary / Caretaker / Allrounder / Bruiser / Wrecker")
        if existing:
            taken = ", ".join(sorted({c.name for c in existing}))
            print(f"Already in deck: {taken}\n")

        damage = prompt_int("Damage points", 0, budget)
        heal = budget - damage
        print(f"  -> Heal points auto-set to {heal}")
        try:
            card = craft_card(
                card_id,
                damage,
                power_points,
                existing,
                steals=steals,
                heavy_hit=heavy_hit,
            )
        except ValueError as exc:
            print(f"  -> {exc}")
            pause()
            continue
        print(f"  -> Auto-named: {card.name}")
        if card.steals:
            print("  -> Steal: takes 1 opponent card for 1 turn")
        if card.heavy_hit:
            print("  -> Heavy Hit: +50% power, 2-turn cooldown, clears target cooldowns for 2 turns")
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


def create_player_deck(player_num: int, total_players: int, power_points: int) -> list[Card]:
    clear()
    banner(f"Card Lab — player-{player_num}/{total_players}")
    print(f"player-{player_num}, build your deck of 5 cards.")
    print(f"Cards 1–4: {power_points} power points each.")
    print(f"Card 5: Mercy ({FIFTH_CARD_HEAL} heal, any target).")
    print("After everyone crafts, craftable cards are shuffled and re-dealt.")
    print("Mercy and steal cards always stay with the player who made them.")
    print("Heavy Hit cards also stay with their owner.\n")
    pause()

    deck: list[Card] = []
    for slot in range(1, DECK_SIZE):
        deck.append(create_card(slot, slot, power_points, deck))
    deck.append(create_fifth_card(deck))

    clear()
    banner(f"player-{player_num} Deck Ready")
    for i, card in enumerate(deck, start=1):
        print_card(card, i)
    print()
    pause("Pass the device to the next player...")
    return deck


def create_all_player_decks(player_count: int, power_points: int) -> list[list[Card]]:
    clear()
    banner("Card Lab")
    print(f"Each of the {player_count} players builds a deck of {DECK_SIZE} cards.")
    print(f"Cards 1–4: {power_points} power points each.")
    print(f"Card 5: Mercy ({FIFTH_CARD_HEAL} heal, any target).")
    print("\nWhen everyone is done, craftable cards are combined, shuffled, and dealt.")
    print("Mercy, steal, and Heavy Hit cards stay with whoever crafted them.\n")
    pause()

    return [
        create_player_deck(n, player_count, power_points)
        for n in range(1, player_count + 1)
    ]


def show_deal_summary(players: list[Player]) -> None:
    clear()
    banner("Cards Shuffled & Dealt")
    print("Craftable cards were shuffled and dealt. Mercy/steal stayed with owners.\n")
    for player in players:
        print(f"{player.name}:")
        for i, card in enumerate(player.hand, start=1):
            print_card(card, i)
        print()
    pause()


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
        deck.append(
            create_card(slot, slot, power_points, deck, allow_steal=not for_solo)
        )
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


def resolve_steal_if_needed(
    card: Card,
    players: list[Player],
    active: int,
    target_idx: int,
    borrows: list[ActiveBorrow],
) -> None:
    for line in resolve_steal(card, players, active, target_idx, borrows):
        print(f"  -> {line}")


def play_turn(
    players: list[Player],
    active: int,
    starting_hp: int,
    borrows: list[ActiveBorrow],
) -> list[ActiveBorrow]:
    player = players[active]
    clear()
    banner(f"Turn — {player.name}")
    print_status(players, active)

    playable = player.playable_cards()
    if not playable:
        print(f"{player.name} has no playable cards — turn skipped.")
        player.last_card_id = None
        turn_delay()
        borrows, return_logs = return_expired_borrows(players, active, borrows)
        for line in return_logs:
            print(f"  -> {line}")
        for line in tick_turn_cooldowns(players, active):
            print(f"  -> {line}")
        return borrows

    if player.is_bot:
        print("Bot hand:")
        for i, card in enumerate(player.hand, start=1):
            print_card(card, i, cooling_down=card_is_cooling(player, card))
        print()
        choice = bot_choose_play(players, active, starting_hp)
        if choice is None:
            print("Bot has no playable cards — turn skipped.")
            player.last_card_id = None
            turn_delay()
            borrows, return_logs = return_expired_borrows(players, active, borrows)
            for line in return_logs:
                print(f"  -> {line}")
            for line in tick_turn_cooldowns(players, active):
                print(f"  -> {line}")
            return borrows
        card, target_idx, reason = choice
        mark_card_played(player, card)
        print(f"Bot plan: {reason}\n")
        announce_play(player, card)
        print(f"Targeted: {describe_target(card, players, active, target_idx)}")
        print("\n--- Resolve ---")
        for line in resolve_card(card, players, active, target_idx):
            print(f"  -> {line}")
        resolve_steal_if_needed(card, players, active, target_idx, borrows)
        print()
        print_status(players)
        turn_delay("Ending bot turn...")
        borrows, return_logs = return_expired_borrows(players, active, borrows)
        for line in return_logs:
            print(f"  -> {line}")
        for line in tick_turn_cooldowns(players, active):
            print(f"  -> {line}")
        return borrows

    print("Your cards (reuse allowed; not twice in a row):\n")
    for i, card in enumerate(player.hand, start=1):
        print_card(card, i, cooling_down=card_is_cooling(player, card))
    print()

    while True:
        pick = prompt_int("Play which card #", 1, len(player.hand)) - 1
        card = player.hand[pick]
        if card_is_cooling(player, card):
            print(f"  '{card.name}' is cooling down — pick a different card.")
            continue
        break
    mark_card_played(player, card)
    announce_play(player, card)

    target_idx = choose_target(players, active, card)
    if target_idx is None:
        print("No valid targets.")
    else:
        print(f"Targeted: {describe_target(card, players, active, target_idx)}")
        print("\n--- Resolve ---")
        for line in resolve_card(card, players, active, target_idx):
            print(f"  -> {line}")
        resolve_steal_if_needed(card, players, active, target_idx, borrows)

    print()
    print_status(players)
    turn_delay("Ending turn...")
    borrows, return_logs = return_expired_borrows(players, active, borrows)
    for line in return_logs:
        print(f"  -> {line}")
    for line in tick_turn_cooldowns(players, active):
        print(f"  -> {line}")
    return borrows


def game_loop(players: list[Player], starting_hp: int) -> None:
    active = 0
    borrows: list[ActiveBorrow] = []
    while True:
        if not players[active].alive:
            nxt = next_alive_index(players, active)
            if nxt is None:
                break
            active = nxt
            continue

        pass_device(players[active])
        borrows = play_turn(players, active, starting_hp, borrows)

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

        if settings.vs_bot:
            human_deck = create_shared_deck(
                settings.power_points, for_solo=True
            )
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
            player_decks = create_all_player_decks(
                settings.player_count, settings.power_points
            )
            players = make_players_from_mixed_decks(
                player_decks, settings.starting_hp
            )
            show_deal_summary(players)

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
