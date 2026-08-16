#!/usr/bin/env python3
import sys, json

sys.stdin.reconfigure(encoding="utf-8", errors="surrogateescape")
sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="surrogateescape")
sys.stderr.reconfigure(encoding="utf-8", errors="surrogateescape")
import time


from include.zustand import Config, Position, Zustand, Gem
from include.checks import *
from include.signal_interpreter import (
    calc_candidates,
    check_possible_duos,
    check_possible_swaps,
    get_possible_pairs,
    check_possible_pairs,
    get_possible_triples,
    check_possible_triples,
    check_for_circling,
    get_signal_from_known_gems,
    precalculate_signal_offsets,
    resolve_two_unknown_gems,
)
from include.pathfinding_logics import (
    generate_a_star_path,
    follow_a_star_path,
    get_all_distances_to_bot,
    bfs_distances_from,
    get_mid,
)
from include.highlighting import *
from include.pfad_und_routen import (
    check_for_new_path,
    get_best_reachable_center,
    move_without_gem,
)
from include.clustering import actualize_dict
from include.matrix import (
    initalize_current_matrix,
    initalize_saved_matrix,
    initalize_dict_of_tiles,
    make_current_matrix,
    make_saved_matrix,
    get_current_frontiers,
    get_saved_frontiers,
    reset_matrix_floors,
)


def first_tick(data, zustand: Zustand):
    zustand.config = Config(**data["config"])
    vis_bots = data.get("visible_bots", None)

    if vis_bots is None:
        zustand.with_opponent = False
    else:
        zustand.with_opponent = True

    zustand.mid = Position([zustand.config.width // 2, zustand.config.height // 2])

    initalize_current_matrix(zustand)
    initalize_saved_matrix(zustand)
    initalize_dict_of_tiles(zustand)
    precalculate_signal_offsets(zustand)


def write_zustand(data, zustand: Zustand):
    """Setzt den Zustand basierend auf den empfangenen Spieldaten."""
    start_time = time.perf_counter_ns()
    zustand.tick = data["tick"]
    zustand.bot = Position(data["bot"])
    zustand.initative = data.get("initiative", True)
    zustand.signal_level = data.get("signal_level", 0)
    zustand.signal_level_dict.update({zustand.tick: zustand.signal_level})

    if len(data.get("visible_bots", [])) > 0:
        zustand.opponent = Position(data["visible_bots"][0]["position"])
        zustand.opponent_emoji = data["visible_bots"][0]["emoji"]
    else:
        zustand.opponent = None

    zustand.walls = [Position(wall) for wall in data["wall"]]

    zustand.floors = [Position(floor) for floor in data["floor"]]

    zustand.visible_gems = [Gem(**gem) for gem in data.get("visible_gems", [])]

    # Wenn der Gegner nicht mehr sichtbar ist, auf None setzen und ignorieren
    if zustand.opponent not in zustand.floors:
        zustand.opponent = None

    gems_to_remove = []
    for gem in zustand.remembered_gems:
        gem.ttl -= 1
        if gem.ttl == 0:
            debug_print("Removed cause ttl = 0", zustand)
            gems_to_remove.append(gem)
    for gem in gems_to_remove:
        zustand.remembered_gems.remove(gem)

    for gem in zustand.visible_gems:
        already_in = False
        for remembered_gem in zustand.remembered_gems:
            if gem.position == remembered_gem.position:
                already_in = True
                zustand.remembered_gems.remove(remembered_gem)
                zustand.remembered_gems.append(gem)
                break
        if already_in == False:
            zustand.remembered_gems.append(gem)

    for gem in zustand.remembered_gems:
        if zustand.bot == gem.position:
            zustand.remembered_gems.remove(gem)

    # Entfernen von Gems, die nicht mehr da sind,
    # weil vom Gegner geklaut wurden oder abgelaufen sind
    new_remembered = []
    for remembered_gem in zustand.remembered_gems:
        if (remembered_gem.position in zustand.floors) or (
            remembered_gem.position in zustand.walls
        ):
            # Der remembered_gem ist auf dem Floor,
            # prüfen, ob das Gem noch in visible_gems ist
            is_still_there = False
            for visible_gem in zustand.visible_gems:
                if remembered_gem.position == visible_gem.position:
                    is_still_there = True
                    break
            if is_still_there == True:
                new_remembered.append(remembered_gem)
            # sonst: nicht hinzufügen (wird entfernt)
        else:
            # nicht auf dem Floor -> behalten
            new_remembered.append(remembered_gem)
    zustand.remembered_gems = new_remembered

    actualize_dict(zustand)
    make_saved_matrix(zustand)
    make_current_matrix(zustand)
    get_all_distances_to_bot(zustand)

    all_gem_pos = []
    for gem in zustand.remembered_gems:
        all_gem_pos.append(gem.position)

    # Gems entfernen, die nicht mehr erreichbar sind
    reachable_remembered = []
    for gem in zustand.remembered_gems:
        if gem.position in zustand.distances_to_bot:
            reachable_remembered.append(gem)
    zustand.remembered_gems = reachable_remembered

    get_current_frontiers(zustand)
    if zustand.frontiers == []:
        reset_matrix_floors(zustand)
        make_current_matrix(zustand)
        get_current_frontiers(zustand)
    get_saved_frontiers(zustand)

    residual_signal = zustand.signal_level - get_signal_from_known_gems(zustand)
    # and signal
    if len(zustand.possible_pairs) > 0:
        check_possible_pairs(zustand)
        debug_print("Checking pairs", zustand)
    elif len(zustand.possible_triples) > 0:
        check_possible_triples(zustand)
        debug_print("Checking triples", zustand)

    if len(zustand.possible_duos) > 0:
        check_possible_duos(zustand)
        debug_print("Checking duos", zustand)

    residual_signal = zustand.signal_level - get_signal_from_known_gems(zustand)

    if (
        len(zustand.possible_pairs) == 0
        and len(zustand.possible_triples) == 0
        and abs(residual_signal) > 0.0001
    ):
        # debug_print("Calculating Candidates", zustand)
        calc_candidates(zustand)
        if len(zustand.possible_swaps) > 0:
            check_possible_swaps(zustand)
            debug_print(f"Checking Swaps {len(zustand.possible_swaps)}", zustand)

    else:
        zustand.current_candidates = set()

    if (
        len(zustand.last_candidates) > 0
        and len(zustand.current_candidates) == 0
        and len(zustand.possible_pairs) == 0
        and residual_signal > zustand.last_residual + 0.001
    ):
        get_possible_pairs(zustand)
        debug_print(f"Calculating pairs {len(zustand.possible_pairs)}", zustand)

    elif (
        len(zustand.last_possible_pairs) > 0
        and len(zustand.possible_pairs) == 0
        and len(zustand.possible_triples) == 0
        and residual_signal > zustand.last_residual + 0.001
    ):
        get_possible_triples(zustand)
        debug_print("Calculating triples", zustand)

    if zustand.config.max_gems - len(zustand.remembered_gems) >= 2:
        if (
            len(zustand.possible_pairs) == 0
            and len(zustand.possible_triples) == 0
            and len(zustand.current_candidates) == 0
            and len(zustand.possible_swaps) == 0
        ):
            new_duos = resolve_two_unknown_gems(zustand)
            if len(new_duos) > 0 and len(zustand.possible_duos) == 0:
                debug_print("Konflikt in Kandidaten - Starte Duosuche", zustand)
                zustand.possible_duos = new_duos

    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )


def main():
    """main game loop"""

    zustand = Zustand()
    is_first_tick = True
    midded = False
    zustand.remembered_gems = []

    for line in sys.stdin:
        zustand.start_time = time.perf_counter_ns()
        data = json.loads(line)
        zustand.run_time_analyse = []

        if is_first_tick == True:
            first_tick(data, zustand)
            is_first_tick = False

        write_zustand(data, zustand)

        if (
            check_for_change_gems(zustand) == True
            and check_if_this_tick_has_gem(zustand) == True
        ):
            # Gem aufgetaucht oder einer verschwunden
            check_for_new_path(zustand)
            zustand.a_star_path = generate_a_star_path(
                zustand, zustand.destination, zustand.bot
            )
            move = check_for_circling(zustand)
        elif (
            check_if_this_tick_has_gem(zustand) == True
            and check_for_change_gems(zustand) == False
        ):
            if zustand.with_opponent == False or (
                zustand.last_opponent is None and zustand.opponent is not None
            ):
                check_for_new_path(zustand)
                zustand.a_star_path = generate_a_star_path(
                    zustand, zustand.destination, zustand.bot
                )
            # Wir haben Gems aber es hat sich nichts geändert
            move = check_for_circling(zustand)

        elif check_if_this_tick_has_gem(zustand) == False:
            # Nichts da also erkunden oder mitte
            if zustand.signal_level == 0:
                if zustand.tick > 100:
                    # Nur neue Mitte, wenn sich wes üändern kann
                    if len(zustand.saved_frontiers) > 0 and midded == False:
                        if zustand.with_opponent == True:
                            zustand.mid = get_best_reachable_center(zustand)
                        else:
                            zustand.mid = get_mid(zustand)
                    else:
                        zustand.mid = get_mid(zustand)
                        midded = True
                    zustand.a_star_path = generate_a_star_path(
                        zustand, zustand.mid, zustand.bot
                    )
                    zustand.destination = zustand.mid
                    move = follow_a_star_path(zustand)
                else:
                    move = move_without_gem(zustand)

            else:
                if (
                    len(zustand.current_candidates) > 0
                    or len(zustand.possible_pairs) > 0
                    or len(zustand.possible_points) > 0
                ):
                    if len(zustand.current_candidates) > 0:
                        possible_destinations = zustand.current_candidates
                    elif len(zustand.possible_pairs) > 0:
                        possible_destinations = set()
                        for pair in zustand.possible_pairs:
                            possible_destinations.add(pair["gem_A_pos"])
                            for candidate_B in pair["gem_B_candidates"]:
                                possible_destinations.add(candidate_B)
                    elif len(zustand.possible_points) > 0:
                        possible_destinations = zustand.possible_points

                    least_dist = 10000
                    destination = None
                    if zustand.opponent is not None:
                        used_dists = bfs_distances_from(
                            zustand.opponent, zustand, possible_destinations
                        )
                    else:
                        used_dists = zustand.distances_to_bot
                    for candidate in possible_destinations:
                        dist = used_dists.get(candidate, None)
                        if dist is not None:
                            if dist < least_dist:
                                least_dist = dist
                                destination = candidate
                    if destination is not None:
                        zustand.destination = destination
                        zustand.a_star_path = generate_a_star_path(
                            zustand, zustand.destination, zustand.bot
                        )
                        move = follow_a_star_path(zustand)
                    else:
                        move = move_without_gem(zustand)
                else:
                    move = move_without_gem(zustand)
        else:
            move = "WAIT"

        # Pfad validieren
        if zustand.a_star_path is not None:
            for pos in zustand.a_star_path:
                if zustand.saved_matrix[pos.y][pos.x] == "X":
                    if check_if_destination_in_gems(zustand) == True:
                        check_for_new_path(zustand)
                    zustand.a_star_path = generate_a_star_path(
                        zustand, zustand.destination, zustand.bot
                    )
                    move = follow_a_star_path(zustand)
                    break

        highlight_items = (
            highlight_path(zustand)
            + highlight_gems(zustand.remembered_gems, zustand)
            + highlight_fov([zustand.mid], zustand)
        )
        highlight_message = {"highlight": highlight_items}
        # if zustand.tick % 100 == 0:
        #     highlight_message.update({"command": "pause"})

        if (
            zustand.messaged == False
            and zustand.opponent_emoji != ""
            and zustand.tick > 100
        ):
            zustand.messaged = True
            print(
                "##########################################",
                file=sys.stderr,
                flush=True,
            )
            try:
                if zustand.opponent_emoji in zustand.messages:
                    print(
                        zustand.messages[zustand.opponent_emoji],
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    print(
                        f"Hallo {zustand.opponent_emoji}!",
                        file=sys.stderr,
                        flush=True,
                    )
            except (KeyError, TypeError, UnicodeError):
                print(
                    f"Hallo!",
                    file=sys.stderr,
                    flush=True,
                )
            print(
                "##########################################",
                file=sys.stderr,
                flush=True,
            )

        if zustand.current_candidates is not None and isinstance(
            zustand.current_candidates, (set, dict)
        ):
            zustand.last_candidates = zustand.current_candidates.copy()
        else:
            zustand.last_candidates = (
                set() if isinstance(zustand.current_candidates, set) else {}
            )

        known_signal = get_signal_from_known_gems(zustand)
        residual_signal = zustand.signal_level - known_signal

        zustand.last_residual = residual_signal

        zustand.last_remembered_gems = zustand.remembered_gems.copy()
        zustand.last_possible_pairs = zustand.possible_pairs.copy()

        zustand.last_move = move
        zustand.last_opponent = zustand.opponent
        zustand.last_clusters = zustand.clusters.copy()

        zustand.run_time_analyse.append(
            ["total_tick_time", (time.perf_counter_ns() - zustand.start_time) / 1000000]
        )
        # if (time.perf_counter_ns() - zustand.start_time) / 1000000 > 80:
        #    highlight_message.update({"command": "pause"})
        # debug_print(zustand.run_time_analyse, zustand)

        print(
            move,
            json.dumps(highlight_message),
            flush=True,
        )


if __name__ == "__main__":
    main()
