#!/usr/bin/env python3


# Imports
import time
import math
import sys, json
import random

sys.stdin.reconfigure(encoding="utf-8", errors="surrogateescape")
sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="surrogateescape")
sys.stderr.reconfigure(encoding="utf-8", errors="surrogateescape")


from include.move_without_gems import (
    move_without_gem,
    initalize_checked_matrix,
    actualize_checked_matrix,
)
from include.buffer import (
    check_for_alarm,
    check_taken_gems,
    check_team_buffer,
    find_swarm_gem_to_request,
    precalculate_node_to_bin,
    put_buffer_together,
    put_zeros_infront_and_to_binary,
    read_team_buffer,
    set_team_buffer,
    take_all_needed_gems,
    write_map_update,
    write_offset_to_buffer,
    write_pos_update,
)
from include.prepare_tick import (
    handle_gems,
    set_last_vars,
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
    generate_a_star_path,
    follow_a_star_path,
    get_all_distances_to_bot,
    get_next_field,
    update_wall_cache,
    validate_path,
)
from include.highlighting import *
from include.pfad_und_routen import (
    check_for_new_path,
    generate_permutations,
    set_destination_to_candidate,
)
from include.matrix import (
    initalize_current_matrix,
    initalize_saved_matrix,
    initalize_shared_matrix,
    make_current_matrix,
    make_saved_matrix,
    get_current_frontiers,
    get_saved_frontiers,
    reset_matrix_floors,
)


def first_tick(data, zustand: Zustand):
    """Diese Funktion setzt und erzeugt wichtige Variablen im ersten Tick"""

    zustand.config = Config(**data["config"])

    # Das Randommodul mit einem Seed initialisieren, damit es deterministisch bleibt.
    random.seed(zustand.config.bot_seed)

    # Nur ein Team bedeutet, dass es keinen Gegner gibt.
    if zustand.config.team_count == 1:
        zustand.with_opponent = False
    else:
        zustand.with_opponent = True
        zustand.weights.search_till_tick = 300

    # Variablen mit der korrekten Länge initialisieren
    for _ in range(zustand.config.max_gems):
        zustand.candidates.append(set())
        zustand.no_signal_streak.append(0)
        zustand.discovered_in_tick.append(-1)
        zustand.reseted_channels.append(())

    zustand.mid = (zustand.config.width // 2, zustand.config.height // 2)

    # Teammates auf irgendwelche Positionen setzen, da noch nicht bekannt
    zustand.teammates = [(20, 20)] * 4

    # Eigene Position korrekt setzen
    zustand.teammates[zustand.config.bot_id] = data["bot"]

    zustand.cutoff_dist = (
        math.sqrt(1 / zustand.config.signal_cutoff - 1) * zustand.config.signal_radius
    )

    # Matrizen (Karten) initialisieren
    initalize_current_matrix(zustand)
    initalize_saved_matrix(zustand)
    initalize_checked_matrix(zustand)
    initalize_shared_matrix(zustand)

    # Precalculating Stuff
    precalculate_signal_offsets(zustand)
    generate_permutations(zustand)
    precalculate_node_to_bin(zustand)


def write_zustand(data, zustand: Zustand):
    """Setzt den Zustand basierend auf den empfangenen Spieldaten."""
    # Misst die Zeit zum Debuggen
    start_time = time.perf_counter_ns()

    zustand.run_time_analyse = []

    # Zustand aus Data schreiben
    zustand.tick = data["tick"]
    zustand.bot = tuple(data["bot"])
    zustand.initative = data.get("initiative", True)

    zustand.signal_level = data.get("signal_level", 0)
    zustand.signal_channels = data["channels"]

    # Sets für schneller Check
    zustand.walls = {(w[0], w[1]) for w in data["wall"]}

    zustand.floors = {(f[0], f[1]) for f in data["floor"]}

    # Gems einspeichern
    zustand.visible_gems = [Gem(**gem) for gem in data.get("visible_gems", [])]
    zustand.msgs_in_buffer = []

    # Buffer wird als Array (len=32) mit Dezimalzahlen empfangen und in Binär umgewandelt
    binary_buffer = ""
    for decimal in data["team_buffer"]:
        byte = put_zeros_infront_and_to_binary(decimal, 8)
        binary_buffer += byte

    zustand.team_buffer = binary_buffer

    # if zustand.tick % 20 == 0 and zustand.tick != 0:
    #    zustand.turn -= 1
    #    if zustand.turn == -1:
    #        zustand.turn = 3

    # Schauen, ob sich der Bot aufgehangen hat
    if zustand.bot == zustand.last_last_bot:
        zustand.wobbling_counter += 1
    else:
        zustand.wobbling_counter = 0
    if zustand.wobbling_counter > 4:
        zustand.wobbling = True
        debug_print("Wobbling detected!", zustand)
    else:
        zustand.wobbling = False

    # Sichtbare Gegner einspeichern
    nodes = set()
    for node_set in zustand.gems_and_nodes.values():
        for node in node_set:
            nodes.add(tuple(node))

    zustand.opponents = []
    for bot in data["visible_bots"]:
        if not bot["teammate"]:
            bot["position"] = tuple(bot["position"])
            zustand.opponents.append(bot)
            if zustand.opponent_emoji == "":
                zustand.opponent_emoji = bot["emoji"]

            if bot["position"] in nodes:
                zustand.opponents_on_nodes.update(
                    {tuple(bot["position"]): zustand.tick}
                )

    new_opponents_on_nodes = {}
    for pos, tick in zustand.opponents_on_nodes.items():

        if pos not in nodes:
            continue
        if zustand.tick - tick >= 10:
            continue

        if pos in zustand.floors:
            opp_is_there = False
            for opp in zustand.opponents:
                if tuple(opp["position"]) == pos:
                    opp_is_there = True
                    break
            if not opp_is_there:
                continue

        new_opponents_on_nodes.update({pos: tick})
    zustand.opponents_on_nodes = new_opponents_on_nodes

    # Penaltys updaten

    if len(zustand.remembered_gems) == zustand.config.max_gems:
        zustand.penaltys = {1: 2, 2: 1}
    else:
        zustand.penaltys = {1: 10, 2: 5, 3: 2}

    track_points(zustand)
    # Karten anpassen
    new_walls = make_saved_matrix(zustand)
    make_current_matrix(zustand)
    actualize_checked_matrix(zustand)

    # Buffer
    read_team_buffer(zustand)

    # Wall Cache anpassen
    update_wall_cache(zustand, new_walls)

    get_all_distances_to_bot(zustand)

    check_team_buffer(zustand)

    # Gems beanspruchen
    check_taken_gems(zustand)
    take_all_needed_gems(zustand)

    # Swarmgem Logik
    find_swarm_gem_to_request(zustand)

    handle_gems(zustand)

    check_for_alarm(zustand)

    # Gems sortieren damit Beste zuerst
    if zustand.remembered_gems:
        zustand.remembered_gems.sort(
            key=lambda gem: sort_gems_by_distance(gem, zustand), reverse=True
        )

    # Frontiers berechnen (Stellen die noch zu erkunden sind). Wird nicht genutzt
    get_current_frontiers(zustand)

    # Alles erkundet? Dann Fortschritt in current_matrix resetten
    if zustand.frontiers == []:
        reset_matrix_floors(zustand)
        make_current_matrix(zustand)
        get_current_frontiers(zustand)
    if zustand.saved_frontiers != []:
        get_saved_frontiers(zustand)

    # Unerreichbare Kandidaten aussortieren
    for channel in range(zustand.config.max_gems):
        new_candidates = set()
        for candidate in zustand.candidates[channel]:
            if candidate in zustand.distances_to_bot:
                new_candidates.add(candidate)
        zustand.candidates[channel] = new_candidates

    # Kandidaten berechnen und sortieren
    calc_candidates_for_channels(zustand)
    for channel in range(zustand.config.max_gems):
        if len(zustand.candidates[channel]) > 0:
            zustand.candidates[channel] = set(sorted(zustand.candidates[channel]))

    get_hypothetical_gems_from_candidates(zustand)

    # Gemspawns aufschreiben
    if zustand.tick > 0:
        for channel in range(zustand.config.max_gems):
            if (
                zustand.last_signal_channels[channel] == 0
                and zustand.signal_channels[channel] != 0
            ):
                zustand.total_gems_ttl += zustand.config.gem_ttl

    # Zeitmessung aufschreiben
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )


def main():
    """Main game loop"""
    # Variablen initialisieren
    zustand = Zustand()
    zustand.weights = Weights()
    max_tick_time = 0
    max_buffer_usage = 0
    all_buffer_usages = []

    while True:

        # Daten empfangen
        line = sys.stdin.readline()

        zustand.start_time = time.perf_counter_ns()

        data = json.loads(line)

        if data["tick"] == 0:
            first_tick(data, zustand)

        debug_print(f"#### Bot {zustand.config.bot_id} ####", zustand)

        write_zustand(data, zustand)

        #### Entscheidungsbaum ####

        if zustand.locked == True:
            # Gegner ist gefangen, also nichts tun
            move = follow_a_star_path(zustand)
        elif check_if_this_tick_has_gem(zustand):
            # Zu einem Gem gehen
            check_for_new_path(zustand)
            debug_print(zustand.destination, zustand)
            zustand.a_star_path = generate_a_star_path(
                zustand, zustand.destination, zustand.bot
            )
            move = follow_a_star_path(zustand)
        elif check_if_this_tick_has_gem(zustand) == False:
            # Kein Gem da != Kein Signal
            if zustand.signal_level == 0:
                # Kein Signal
                move_without_gem(zustand)
                move = follow_a_star_path(zustand)
            else:
                # Zu Kandidaten gehen, wenn Signal da ist
                set_destination_to_candidate(zustand)
                move = follow_a_star_path(zustand)

        move = validate_path(zustand, move)
        next_field = get_next_field(zustand, move)

        # Positions/Offset-Update in Buffer schreiben
        if zustand.offset:
            write_pos_update(zustand, next_field)
            zustand.offset = False
            write_offset_to_buffer(zustand, zustand.bot)
        else:
            write_offset_to_buffer(zustand, next_field)

        write_map_update(zustand)

        put_buffer_together(zustand)

        # Highlighting
        highlight_items = get_highlight_items(zustand)

        print_message(zustand)

        print_stats(zustand, max_tick_time, max_buffer_usage, all_buffer_usages)

        tick_time = (time.perf_counter_ns() - zustand.start_time) / 1000000

        if tick_time > max_tick_time and zustand.tick > 1:
            max_tick_time = tick_time

        # Maximale Auslastung des Buffers tracken
        all_buffer_usages.append(32 * 8 - zustand.bits_left)
        if 32 * 8 - zustand.bits_left > max_buffer_usage:
            max_buffer_usage = 32 * 8 - zustand.bits_left

        # Bewegung, Buffer und Highlights an Runner senden
        command = print_log(zustand, tick_time, {"highlight": highlight_items})
        command.update({"comm": set_team_buffer(zustand)})
        highlight_msg = json.dumps(command)
        output_line = f"{move} {highlight_msg}\n"
        sys.stdout.write(output_line)
        sys.stdout.flush()

        set_last_vars(zustand, move)


if __name__ == "__main__":
    main()
