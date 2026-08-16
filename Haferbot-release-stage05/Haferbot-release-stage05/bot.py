#!/usr/bin/env python3

import time
import math
import sys, json
import random

sys.stdin.reconfigure(encoding="utf-8", errors="surrogateescape")
sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="surrogateescape")
sys.stderr.reconfigure(encoding="utf-8", errors="surrogateescape")


from include.prepare_tick import (
    connect_portals,
    handle_gems,
    save_opponent_portals,
    set_last_vars,
    track_opponent,
    track_points,
)


from include.zustand import Config, Weights, Zustand, Gem
from include.checks import *
from include.signal_interpreter import (
    calc_candidates_for_channels,
    get_hypothetical_gems_from_candidates,
    precalculate_signal_offsets,
    sort_gems_by_distance,
)
from include.pathfinding_logics import (
    bfs_distances_from,
    generate_a_star_path,
    follow_a_star_path,
    get_all_distances_to_bot,
    update_wall_cache,
    validate_path,
)
from include.highlighting import *
from include.pfad_und_routen import (
    check_for_new_path,
    generate_permutations,
    get_dist_to_next_mid_portal,
    get_nearest_border_portal,
    get_nearest_unknown_opponent_portal,
    go_to_or_place_midportal,
    move_without_gem,
    place_border_portal,
    set_destination_to_candidate,
    set_path_to_mid,
    go_to_unknown_opponent_portal,
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
        zustand.weights.search_till_tick = 300

    for _ in range(zustand.config.max_gems):
        zustand.candidates.append([set()])
        zustand.discovered_in_tick.append(-1)
        zustand.reseted_channels.append(())

    zustand.mid = (zustand.config.width // 2, zustand.config.height // 2)

    factor = 1 / math.sqrt(3)
    sigma_step = zustand.config.signal_noise * factor
    zustand.weights.s_error_margin = sigma_step * 3

    zustand.weights.p_claimed_fields_min = 45 if zustand.with_opponent == False else 39
    zustand.weights.p_dist_min = (
        math.ceil((zustand.config.width + 5) / 2)
        if zustand.with_opponent == False
        else 19
    )

    initalize_current_matrix(zustand)
    initalize_saved_matrix(zustand)
    initalize_dict_of_tiles(zustand)
    precalculate_signal_offsets(zustand)
    generate_permutations(zustand)


def write_zustand(data, zustand: Zustand):
    """Setzt den Zustand basierend auf den empfangenen Spieldaten."""
    start_time = time.perf_counter_ns()

    zustand.run_time_analyse = []
    zustand.tick = data["tick"]
    zustand.bot = tuple(data["bot"])
    zustand.initative = data.get("initiative", True)

    zustand.signal_level = data.get("signal_level", 0)
    zustand.signal_channels = data["channels"]

    zustand.walls = {(w[0], w[1]) for w in data["wall"]}

    zustand.floors = {(f[0], f[1]) for f in data["floor"]}

    zustand.visible_gems = [Gem(**gem) for gem in data.get("visible_gems", [])]
    zustand.visible_portals = [tuple(p) for p in data["portals"]]
    zustand.portal_stubs = [tuple(p) for p in data["portal_stubs"]]

    if zustand.tick % 50 == 0 and zustand.tick > 0:
        zustand.weights.p_claimed_fields_min -= 2
        zustand.weights.p_dist_min -= 1

    zustand.any_portals |= set(zustand.visible_portals)
    zustand.any_portals |= set(zustand.portal_stubs)
    zustand.any_full_portals |= set(zustand.visible_portals)

    # Wenn der Gegner nicht mehr sichtbar ist, auf None setzen und ignorieren
    if zustand.opponent not in zustand.floors:
        zustand.opponent = None

    if len(zustand.remembered_gems) == zustand.config.max_gems:
        zustand.penaltys = {1: 2, 2: 1}
    else:
        zustand.penaltys = {1: 10, 2: 5, 3: 2}

    track_points(zustand)
    actualize_dict(zustand)
    new_walls = make_saved_matrix(zustand)
    make_current_matrix(zustand)
    update_wall_cache(zustand, new_walls)

    save_opponent_portals(zustand)

    zustand.unknown_opponent_portals = (
        zustand.any_full_portals
        - set(p[0] for p in zustand.mid_portals)
        - set(p[0] for p in zustand.border_portals)
        - set(p for p in zustand.solved_opponent_portals)
    )

    connect_portals(zustand)

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
        zustand.weights.search_till_tick = 0
        zustand.weights.p_claimed_fields_min = 25
        zustand.weights.p_dist_min = 10
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
    zustand.weights = Weights()
    max_tick_time = 0

    while True:

        line = sys.stdin.readline()

        if not line:
            break

        zustand.start_time = time.perf_counter_ns()

        data = json.loads(line)

        if data["tick"] == 0:
            first_tick(data, zustand)

        write_zustand(data, zustand)

        if len(zustand.border_portals) < zustand.config.max_portals:
            border_portal = get_nearest_border_portal(zustand)

        if check_if_this_tick_has_gem(zustand):
            dist_nearest_gem = min(
                zustand.distances_to_bot[gem.position]
                for gem in zustand.remembered_gems + zustand.hypothetical_gems
            )
            if zustand.opponent is not None:
                dist_gem_opp = min(
                    bfs_distances_from(
                        zustand.opponent,
                        zustand,
                        [
                            gem.position
                            for gem in zustand.remembered_gems
                            + zustand.hypothetical_gems
                        ],
                    )[gem.position]
                    for gem in zustand.remembered_gems + zustand.hypothetical_gems
                )
            else:
                dist_gem_opp = float("inf")
                _, dist_to_oppenent_portal, _ = get_nearest_unknown_opponent_portal(
                    zustand
                )

        else:
            dist_nearest_gem = float("inf")

        #### Entscheidungsbaum ####

        if zustand.locked == True:
            # Gegner ist gefangen, also nichts tun
            move = follow_a_star_path(zustand)
        elif (
            zustand.with_opponent
            and len(zustand.unknown_opponent_portals) > 0
            and (
                len(zustand.remembered_gems + zustand.hypothetical_gems) == 0
                or (zustand.opponent is not None and dist_nearest_gem > dist_gem_opp)
                or (
                    zustand.opponent is None
                    and dist_nearest_gem > dist_to_oppenent_portal + 3
                )
            )
        ):
            move = go_to_unknown_opponent_portal(zustand)

        elif (
            len(zustand.mid_portals) < zustand.config.max_portals
            and get_dist_to_next_mid_portal(zustand)
            < zustand.weights.max_dist_mid_portal
        ):
            # Mid Portal platzieren oder dorthin gehen
            move = go_to_or_place_midportal(zustand)
        elif (
            len(zustand.border_portals) < zustand.config.max_portals
            and border_portal is not None
            and zustand.distances_to_bot[border_portal]
            < zustand.weights.max_dist_border_portal
            and len(zustand.mid_portals) > 0
            and (
                (
                    check_if_this_tick_has_gem(zustand)
                    and dist_nearest_gem > zustand.distances_to_bot[border_portal] + 4
                )
                or (
                    check_if_this_tick_has_gem(zustand) == False
                    and (
                        (
                            zustand.signal_level == 0
                            and zustand.tick < zustand.weights.search_till_tick
                        )
                        or (zustand.signal_level > 0)
                    )
                )
            )
        ):
            # Border Portal platzieren oder dorthin gehen
            if zustand.bot == border_portal:
                move = place_border_portal(zustand)
            else:
                zustand.destination = border_portal
                zustand.a_star_path = generate_a_star_path(
                    zustand, zustand.destination, zustand.bot
                )
                move = follow_a_star_path(zustand)
        elif check_if_this_tick_has_gem(zustand):
            # Zu einem Gem gehen
            check_for_new_path(zustand)
            zustand.a_star_path = generate_a_star_path(
                zustand, zustand.destination, zustand.bot
            )
            move = follow_a_star_path(zustand)
        elif check_if_this_tick_has_gem(zustand) == False:
            # Kein Gem da != Kein Signal
            if zustand.signal_level == 0:
                if (
                    zustand.with_opponent == True
                    and len(zustand.border_portals) < zustand.config.max_portals
                    and zustand.tick < zustand.weights.search_till_tick
                ) or (
                    zustand.with_opponent == False
                    and (
                        len(zustand.border_portals) < zustand.config.max_portals - 1
                        or zustand.tick < zustand.weights.search_till_tick
                    )
                ):
                    # Frühes Spiel also erstmal erkunden
                    move_without_gem(zustand)
                else:
                    # Nichts da also mitte
                    set_path_to_mid(zustand)
                move = follow_a_star_path(zustand)
            else:
                # Zu Kandidaten gehen, wenn Signal da ist
                set_destination_to_candidate(zustand)
                move = follow_a_star_path(zustand)

        move = validate_path(zustand, move)

        highlight_items = get_highlight_items(zustand)

        print_message(zustand)

        print_stats(zustand, max_tick_time)

        tick_time = (time.perf_counter_ns() - zustand.start_time) / 1000000
        if tick_time > max_tick_time and zustand.tick > 1:
            max_tick_time = tick_time

        command = print_log(zustand, tick_time, {"highlight": highlight_items})

        highlight_msg = json.dumps(command)
        output_line = f"{move} {highlight_msg}\n"
        sys.stdout.write(output_line)
        sys.stdout.flush()

        set_last_vars(zustand, move)


if __name__ == "__main__":
    main()
