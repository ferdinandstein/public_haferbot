#!/usr/bin/env python3
import math
import sys, json
import random
import uuid

from include.prepare_tick import (
    handle_gems,
    set_last_vars,
    track_opponent,
    track_points,
)

sys.stdin.reconfigure(encoding="utf-8", errors="surrogateescape")
sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="surrogateescape")
sys.stderr.reconfigure(encoding="utf-8", errors="surrogateescape")
import time


from include.zustand import Config, Zustand, Gem
from include.checks import *
from include.signal_interpreter import (
    calc_candidates_for_channels,
    get_hypothetical_gems_from_candidates,
    precalculate_signal_offsets,
    sort_gems_by_distance,
)
from include.pathfinding_logics import (
    approximate_mid,
    generate_a_star_path,
    follow_a_star_path,
    get_all_distances_to_bot,
    select_best_field_with_opponent,
    update_wall_cache,
)
from include.highlighting import *
from include.pfad_und_routen import (
    check_for_new_path,
    generate_permutations,
    move_without_gem,
    set_destination_to_candidate,
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
    random.seed(zustand.config.bot_seed)

    vis_bots = data.get("visible_bots", None)

    if vis_bots is None:
        zustand.with_opponent = False
    else:
        zustand.with_opponent = True

    for _ in range(zustand.config.max_gems):
        zustand.candidates.append([set()])
        zustand.discovered_in_tick.append(-1)
        zustand.reseted_channels.append(())

    zustand.mid = (zustand.config.width // 2, zustand.config.height // 2)

    initalize_current_matrix(zustand)
    initalize_saved_matrix(zustand)
    initalize_dict_of_tiles(zustand)
    precalculate_signal_offsets(zustand)
    generate_permutations(zustand)


def write_zustand(data, zustand: Zustand):
    """Setzt den Zustand basierend auf den empfangenen Spieldaten."""
    start_time = time.perf_counter_ns()
    zustand.tick = data["tick"]
    zustand.bot = tuple(data["bot"])
    zustand.initative = data.get("initiative", True)

    zustand.signal_level = data.get("signal_level", 0)
    zustand.signal_channels = data["channels"]

    zustand.walls = {(w[0], w[1]) for w in data["wall"]}

    zustand.floors = {(f[0], f[1]) for f in data["floor"]}

    zustand.visible_gems = [Gem(**gem) for gem in data.get("visible_gems", [])]
    # Wenn der Gegner nicht mehr sichtbar ist, auf None setzen und ignorieren
    if zustand.opponent not in zustand.floors:
        zustand.opponent = None

    if len(zustand.remembered_gems) > 4:
        zustand.penaltys = {1: 2, 2: 1}
    else:
        zustand.penaltys = {1: 10, 2: 5, 3: 2}

    track_points(zustand)
    actualize_dict(zustand)
    new_walls = make_saved_matrix(zustand)
    make_current_matrix(zustand)
    update_wall_cache(zustand, new_walls)

    if len(data.get("visible_bots", [])) > 0:
        zustand.opponent = tuple(data["visible_bots"][0]["position"])
        zustand.opponent_emoji = data["visible_bots"][0]["emoji"]
        zustand.opponent_area = set()
        zustand.opponent_area.add(zustand.opponent)
    else:
        zustand.opponent = None
        track_opponent(zustand)

    get_all_distances_to_bot(zustand)
    handle_gems(zustand)

    if zustand.remembered_gems:
        zustand.remembered_gems.sort(
            key=lambda gem: sort_gems_by_distance(gem, zustand), reverse=True
        )
    get_current_frontiers(zustand)

    if zustand.frontiers == []:
        reset_matrix_floors(zustand)
        make_current_matrix(zustand)
        get_current_frontiers(zustand)
    if zustand.saved_frontiers != []:
        get_saved_frontiers(zustand)

    calc_candidates_for_channels(zustand)
    for channel in range(zustand.config.max_gems):
        zustand.candidates[channel] = set(sorted(zustand.candidates[channel]))
    get_hypothetical_gems_from_candidates(zustand)

    if zustand.tick > 0:
        for channel in range(zustand.config.max_gems):
            if (
                zustand.last_signal_channels[channel] == 0
                and zustand.signal_channels[channel] != 0
            ):
                zustand.total_gems_ttl += zustand.config.gem_ttl

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
    max_tick_time = 0

    while True:

        line = sys.stdin.readline()

        if not line:
            break

        zustand.start_time = time.perf_counter_ns()

        data = json.loads(line)
        zustand.run_time_analyse = []

        if is_first_tick == True:
            first_tick(data, zustand)
            is_first_tick = False

        write_zustand(data, zustand)

        if zustand.locked == True:
            move = follow_a_star_path(zustand)

        elif (
            check_for_change_gems(zustand) == True
            and check_if_this_tick_has_gem(zustand) == True
        ):
            # Gem aufgetaucht oder einer verschwunden
            old_dest_x, old_dest_y = zustand.destination[0], zustand.destination[1]
            check_for_new_path(zustand)
            path_blocked = False
            if zustand.a_star_path:
                for pos in zustand.a_star_path:
                    if zustand.saved_matrix[pos[1]][pos[0]] == "X":
                        path_blocked = True
                        break

            # A* neu berechnen, wenn sich das Ziel geändert hat ODER der alte Weg blockiert ist
            if (
                old_dest_x != zustand.destination[0]
                or old_dest_y != zustand.destination[1]
            ) or path_blocked:
                zustand.a_star_path = generate_a_star_path(
                    zustand, zustand.destination, zustand.bot
                )

            move = follow_a_star_path(zustand)
        elif (
            check_if_this_tick_has_gem(zustand) == True
            and check_for_change_gems(zustand) == False
        ):
            # Bot bewegt sich stur nach Plan
            if (
                zustand.with_opponent == False
                or zustand.tick % 5 == 0
                or (zustand.last_opponent is None and zustand.opponent is not None)
            ):
                old_dest = zustand.destination
                check_for_new_path(zustand)

                path_blocked = False
                if zustand.a_star_path:
                    for pos in zustand.a_star_path:
                        if zustand.saved_matrix[pos[1]][pos[0]] == "X":
                            path_blocked = True
                            break

                # A* neu berechnen, wenn sich das Ziel geändert hat ODER der alte Weg blockiert ist
                if (zustand.destination != old_dest) or path_blocked:
                    zustand.a_star_path = generate_a_star_path(
                        zustand, zustand.destination, zustand.bot
                    )

            move = follow_a_star_path(zustand)

        elif check_if_this_tick_has_gem(zustand) == False:
            # Nichts da also erkunden oder mitte
            if zustand.signal_level == 0:
                if zustand.tick > 100:
                    # Nur neue Mitte, wenn sich was ändern kann
                    if zustand.opponent is not None:
                        zustand.destination = select_best_field_with_opponent(zustand)
                    else:
                        if len(zustand.saved_frontiers) > 0:
                            zustand.mid = approximate_mid(zustand)
                        elif midded == False:
                            zustand.mid = approximate_mid(zustand)
                            midded = True
                        zustand.destination = zustand.mid
                    zustand.a_star_path = generate_a_star_path(
                        zustand, zustand.destination, zustand.bot
                    )
                    move = follow_a_star_path(zustand)
                else:
                    move_without_gem(zustand)
                    move = follow_a_star_path(zustand)
            else:
                set_destination_to_candidate(zustand)
                move = follow_a_star_path(zustand)
        else:
            move = "WAIT"

        # Pfad validieren
        if zustand.a_star_path is not None:
            for pos in zustand.a_star_path:
                if zustand.saved_matrix[pos[1]][pos[0]] == "X":
                    zustand.a_star_path = generate_a_star_path(
                        zustand, zustand.destination, zustand.bot
                    )
                    move = follow_a_star_path(zustand)
                    break

        if zustand.debug_enabled == True and (
            sys.platform == "win32" or (uuid.getnode() == 9619529777783)
        ):
            highlight_items = (
                highlight_matrix(zustand.saved_matrix, zustand)
                + highlight_path(zustand)
                + highlight_gems(zustand.remembered_gems, zustand)
                + highlight_candidates(zustand)
                + highlight_gems(zustand.hypothetical_gems, zustand)
                # + highlight_opponent(zustand)
            )
            if zustand.mid:
                highlight_items += [[zustand.mid[0], zustand.mid[1], "#04FF00"]]
        else:
            highlight_items = []

        print_message(zustand)

        print_stats(zustand, max_tick_time)

        tick_time = (time.perf_counter_ns() - zustand.start_time) / 1000000

        if tick_time > max_tick_time and zustand.tick > 1:

            max_tick_time = tick_time

        command = {"highlight": highlight_items}
        if (
            zustand.debug_enabled
            and (time.perf_counter_ns() - zustand.start_time) / 1000000 > 800
        ):
            top = 0
            diff = 0
            for item in zustand.run_time_analyse:
                if (
                    item[0] == "write_zustand"
                    or item[0] == "get_route_by_permutations_for_bot"
                    or item[0] == "generate_a_star_path"
                ):
                    top += item[1]
                    debug_print(
                        f"{item[0]}: {item[1]}ms (diff: {(item[1] - diff):.2f}ms)",
                        zustand,
                    )
                    diff = 0
                else:
                    diff += item[1]
                    if len(item) > 2:
                        debug_print(
                            f"---{item[0]}: {item[1]}ms (count: {item[2]})", zustand
                        )
                    else:
                        debug_print(f"---{item[0]}: {item[1]}ms", zustand)

            debug_print(f"Write Zustand + Route + Astar: {top:.2f}ms", zustand)
            debug_print(f"Total Tick Time: {tick_time}ms", zustand)
            debug_print(f"Differenz: {(tick_time - top):.2f}ms", zustand)
            command.update({"command": "pause"})

        highlight_msg = json.dumps(command)
        output_line = f"{move} {highlight_msg}\n"
        sys.stdout.write(output_line)
        sys.stdout.flush()
        #
        set_last_vars(zustand, move)


if __name__ == "__main__":
    main()
