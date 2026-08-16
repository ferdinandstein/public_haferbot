# Berechnet die beste Route zu den Edelsteinen
import math
import random

from include.move_without_gems import move_without_gem
from include.signal_interpreter import sort_gems_by_distance
from include.zustand import Gem, Zustand
from include.pathfinding_logics import (
    bfs_distances_from,
    generate_a_star_path,
    multi_source_a_star,
    select_best_field_with_opponent,
)
from include.highlighting import debug_print
from itertools import permutations


def check_for_new_path(zustand: Zustand):
    if len(zustand.opponents) > 10:
        get_path_with_opponent(zustand)
    else:
        used_gems = []
        blocked_channels = set()
        swarm_gem = False
        if len(zustand.approved_swarm_gem) > 0:
            count, gem, _ = zustand.approved_swarm_gem

            if count == 3:
                ttl = gem.ttl * zustand.config.swarm_score_two_nodes
            elif count == 4:
                ttl = gem.ttl * zustand.config.swarm_score_three_nodes
            used_gems.append(
                Gem(
                    position=gem.position,
                    ttl=ttl,
                    type="swarm",
                    channel=gem.channel,
                )
            )
            blocked_channels.add(gem.channel)
            furthest_bot_dist = 0
            dists = bfs_distances_from(
                gem.position,
                zustand,
                zustand.teammates
                + [
                    g.position
                    for g in zustand.gems_in_buffer
                    if g.channel not in blocked_channels
                ],
            )
            bot_dists = []
            for i in range(4):
                bot_dists.append(dists[zustand.teammates[i]])

            bot_dists.sort(reverse=True)
            if count == 3:
                furthest_bot_dist = bot_dists[1]
            else:
                furthest_bot_dist = bot_dists[0]

            for gem in zustand.gems_taken:
                if (
                    gem.type_ == "regular"
                    and gem.channel not in blocked_channels
                    and zustand.distances_to_bot.get(gem.position) is not None
                    and dists.get(gem.position) is not None
                    and zustand.distances_to_bot[gem.position] + dists[gem.position]
                    < furthest_bot_dist + 3
                ):
                    used_gems.append(gem)
                blocked_channels.add(gem.channel)
            swarm_gem = True

        if zustand.with_opponent:
            debug_print("With opp", zustand)
            for gem in zustand.gems_in_buffer:
                if gem.type_ == "swarm":
                    if len(zustand.gems_and_nodes.get(gem.position, [])) != 3:
                        zustand.gems_and_nodes.update({gem.position: gem.nodes})
                        continue

                    taken = 0
                    for node in zustand.gems_and_nodes[gem.position]:
                        if tuple(node) in zustand.opponents_on_nodes.keys():
                            taken += 1

                    if gem.position == (26, 24):
                        debug_print(taken, zustand)
                    if taken >= 2:
                        for s_gem, tick in zustand.used_swarm_gems:
                            if s_gem.position == gem.position:
                                zustand.used_swarm_gems.remove((s_gem, tick))
                                break
                        gem.type_ = "regular"
                        debug_print(
                            f"Snatching Gem from Opponent: {gem.position}", zustand
                        )
                        zustand.used_swarm_gems.append((gem, zustand.tick))

            new_gems = []
            for gem, tick in zustand.used_swarm_gems:
                if zustand.tick - tick > 10:
                    continue
                still_there = False
                for b_gem in zustand.gems_in_buffer:
                    if b_gem.position == gem.position:
                        still_there = True
                        break
                if not still_there:
                    continue

                new_gems.append((gem, tick))

                used_gems.append(gem)
                blocked_channels.add(gem.channel)

        if not swarm_gem:
            for gem in zustand.gems_taken:

                if gem.type_ == "regular" and gem.channel not in blocked_channels:
                    used_gems.append(gem)
                blocked_channels.add(gem.channel)

            for gem in zustand.remembered_gems:
                if gem.channel not in blocked_channels and gem.type_ == "regular":
                    used_gems.append(gem)
                blocked_channels.add(gem.channel)

        # for gem in zustand.hypothetical_gems:
        #    if (
        #       gem.ttl - zustand.distances_to_bot.get(gem.position, 1000) >= 0
        #        and gem.type_ == "regular"
        #        and gem.channel not in blocked_channels
        #     ):
        #        used_gems.append(gem)

        used_gems.sort(
            key=lambda gem: sort_gems_by_distance(gem, zustand), reverse=True
        )
        if len(used_gems) == 0:
            if zustand.signal_level == 0 and all(
                len(candidates) == 0 for candidates in zustand.candidates
            ):
                move_without_gem(zustand)
            else:
                set_destination_to_candidate(zustand)
        else:
            set_path_to_gem(zustand, used_gems)


def get_route_by_permutations_for_bot(
    position: tuple, used_gems, zustand: Zustand
):  # C Mitgabe Botposition und der benutzten Data (normal oder modifiziert)
    import time

    start_time = time.perf_counter_ns()
    gems_count = len(used_gems)  # C zählt gems in der Data
    if gems_count == 0:  # C wenn 0 gems da rückgabe None
        return None
    else:
        if gems_count > zustand.config.max_gems:
            gems_count = zustand.config.max_gems
        permutations = zustand.permutations[gems_count]

        gem_positions = [g.position for g in used_gems]

        # 1. Berechne Distanzen vom Bot zu allen Gems
        # Das gibt uns ein Dict: {gem_pos: distanz, ...}
        if position == zustand.bot:
            dist_bot_to_gems = zustand.distances_to_bot
        else:
            dist_bot_to_gems = multi_source_a_star(position, zustand, gem_positions)

        # 2. Berechne Distanzen von jedem Gem zu jedem anderen Gem
        # Das ist wichtig für die Wege zwischen den Steinen
        dist_gem_to_gems = get_distance_matrix(zustand, gem_positions)

        # ---------------------------------------------------------

        precomputed_gems = []

        for gem in used_gems:
            multiplier = 1.0
            if zustand.config.max_gems < 8 and gem.channel != -1:
                candidates = max(
                    1, len(zustand.candidates[gem.channel]) - zustand.weights.r_border
                )
                multiplier = 1 / (
                    1
                    + math.pow(
                        candidates / zustand.weights.r_teiler, zustand.weights.r_exp
                    )
                )

            precomputed_gems.append(
                {
                    "pos": gem.position,
                    "ttl": gem.ttl,
                    "multiplier": multiplier,
                    "type": gem.type_,
                }
            )
        max_ttl = max(gem["ttl"] for gem in precomputed_gems)

        time_loop = time.perf_counter_ns()
        best_route = None  # C später für Speicherung der optimalsten Route
        for route in permutations:
            # C Jede Reihenfolge der Edelsteine soll genommen werden
            total_route_distance = 0  # C Variablen zum Speichern der Distanz
            total_route_points = 0
            real_total_route_points = 0

            route_is_valid = True  # Check, ob Weg durch Wände blockiert ist

            for i, gem_index in enumerate(route):
                idx = gem_index - 1
                gem_data = precomputed_gems[idx]
                target_pos = gem_data["pos"]
                type_ = gem_data["type"]
                distance = None

                if i == 0:
                    # Fall 1: Vom Bot zum ersten Stein
                    distance = dist_bot_to_gems[target_pos]
                else:
                    # Fall 2: Von Stein zu Stein
                    # Vorheriger Stein
                    prev_gem_index = route[i - 1]
                    prev_pos = precomputed_gems[prev_gem_index - 1]["pos"]

                    # Hole Distanz aus der Matrix (Von Prev -> Target)
                    if prev_pos in dist_gem_to_gems:
                        distance = dist_gem_to_gems[prev_pos][target_pos]

                # WICHTIG: Wenn distance None ist, ist der Weg durch eine Wand blockiert!
                if distance is None:
                    route_is_valid = False
                    break  # Diese Route abbrechen, sie ist unmöglich

                # Berechnung wie gehabt, aber mit echter Distanz
                total_route_distance += distance

                if (zustand.tick + total_route_distance) > zustand.config.max_ticks:
                    total_route_distance -= distance
                    break

                ttl_loss_per_tick = 1 if type_ == "regular" else 0.5
                evaluated_points = (
                    (gem_data["ttl"] - total_route_distance * ttl_loss_per_tick)
                    * gem_data["multiplier"]
                    # * ((1 - i / 3000))
                )

                if evaluated_points <= 0:
                    break

                total_route_points += evaluated_points
                real_total_route_points += evaluated_points
                if (
                    best_route is not None
                    and (gems_count - (i + 1)) * max_ttl + total_route_points
                    < best_route[0]
                ):
                    break

            # Nur wenn die Route valide war (keine Wände im Weg), vergleichen wir sie
            if route_is_valid:
                wert = (
                    total_route_points
                    - total_route_distance * zustand.weights.r_dist_points_factor
                )
                if best_route is None or wert > best_route[0]:
                    best_route = (
                        wert,
                        total_route_distance,
                        route,
                        real_total_route_points,
                    )
        import inspect

        zustand.run_time_analyse.append(
            [
                "Loop",
                (time.perf_counter_ns() - time_loop) / 1000000,
            ]
        )

        zustand.run_time_analyse.append(
            [
                inspect.currentframe().f_code.co_name,
                (time.perf_counter_ns() - start_time) / 1000000,
            ]
        )

        return best_route  # C effizienteste Route wird zurückgegeben


def get_distance_matrix(zustand: Zustand, used_gems):
    matrix = {gem_pos: {} for gem_pos in used_gems}

    for index, gem_pos in enumerate(used_gems):
        if index == len(used_gems) - 1:
            break
        needed_targets = used_gems[index + 1 :]
        dictionary = multi_source_a_star(gem_pos, zustand, needed_targets)
        matrix[gem_pos].update(dictionary)
        for key, dist in dictionary.items():
            matrix[key][gem_pos] = dist

    return matrix


def set_destination_to_candidate(zustand: Zustand):
    # gehe zu Kandidaten
    active_channels = [
        (candidates, index)
        for index, candidates in enumerate(zustand.candidates)
        if len(candidates) > 0
    ]

    # 2. Diese Liste sortieren: Der Kanal mit den wenigsten Kandidaten zuerst
    active_channels.sort(key=lambda channel: len(channel[0]))
    if active_channels:
        possible_destinations = active_channels[0][0]
        random.shuffle(list(possible_destinations))
        channel = active_channels[0][1]
        points = zustand.config.gem_ttl - (
            zustand.tick - zustand.discovered_in_tick[channel]
        )
        least_dist = 10000
        destination = None
        used_dists = zustand.distances_to_bot
        for candidate in possible_destinations:
            dist = used_dists.get(candidate, None)
            if dist is not None and dist < points and dist < least_dist:
                least_dist = dist
                destination = candidate
        if destination is not None:
            zustand.destination = destination
            zustand.a_star_path = generate_a_star_path(
                zustand, zustand.destination, zustand.bot
            )
        else:
            move_without_gem(zustand)
    else:
        move_without_gem(zustand)


def get_path_with_opponent(zustand: Zustand):
    used_gems_our = [
        gem
        for gem in (zustand.remembered_gems + zustand.hypothetical_gems)
        if gem.ttl - zustand.distances_to_bot.get(gem.position, 1000) >= 0
    ]

    used_gems_our.sort(
        key=lambda gem: sort_gems_by_distance(gem, zustand), reverse=True
    )

    if len(used_gems_our) == 0:
        set_destination_to_candidate(zustand)
    else:
        used_gems_opp = zustand.remembered_gems + zustand.hypothetical_gems
        g_positions = []
        for g in used_gems_opp:
            g_positions.append(g.position)

        dict_opponent = bfs_distances_from(zustand.opponent, zustand, g_positions)

        used_gems_opp = [
            gem
            for gem in (zustand.remembered_gems + zustand.hypothetical_gems)
            if gem.ttl - dict_opponent.get(gem.position, 1000) >= 0
        ]

        used_gems_opp.sort(
            key=lambda gem: dict_opponent.get(gem.position, 1000), reverse=True
        )

        route_for_us = get_route_by_permutations_for_bot(
            zustand.bot, used_gems_our, zustand
        )
        route_for_opponent = get_route_by_permutations_for_bot(
            zustand.opponent, used_gems_opp, zustand
        )
        if route_for_us is None:
            set_destination_to_candidate(zustand)
            return

        if route_for_opponent is None:
            gem = route_for_us[2][0]
            gems_position = used_gems_our[gem - 1].position
            zustand.destination = gems_position
            return

        if (
            used_gems_opp[route_for_opponent[2][0] - 1].position
            == used_gems_our[route_for_us[2][0] - 1].position
        ):  # C route_for...[2] sind die angesteuerten gems, [0] der 1.
            ## Wenn beide den ersten selben gem haben
            gem = route_for_us[2][0]
            gems_position = used_gems_our[gem - 1].position
            distance_for_us = zustand.distances_to_bot.get(gems_position, 1000)
            distance_for_opponent = dict_opponent.get(gems_position, 1000)

            if distance_for_us < distance_for_opponent:
                zustand.destination = gems_position
            elif distance_for_us == distance_for_opponent:
                if distance_for_us % 2 == 0:
                    last_initative = not zustand.initative
                else:
                    last_initative = zustand.initative
                if last_initative == True:
                    zustand.destination = gems_position
                else:
                    ### Wenn der gegnerische Bot zuerst am nächsten gem ankäme und der eigene bot da auch hin will, aber länger braucht, dann wird nun die Route neuberechnet, so dass der eine Gem nicht mit ein berechnet wird.
                    modified_gems = used_gems_our.copy()
                    modified_gems.pop(gem - 1)
                    new_route = get_route_by_permutations_for_bot(
                        zustand.bot, modified_gems, zustand
                    )
                    if new_route is None:
                        zustand.destination = gems_position
                    else:
                        gem = new_route[2][0]
                        gems_position = modified_gems[gem - 1].position
                        zustand.destination = gems_position

            else:
                ### Wenn der gegnerische Bot zuerst am nächsten gem ankäme und der eigene bot da auch hin will, aber länger braucht, dann wird nun die Route neuberechnet, so dass der eine Gem nicht mit ein berechnet wird.
                modified_gems = used_gems_our.copy()
                modified_gems.pop(gem - 1)
                new_route = get_route_by_permutations_for_bot(
                    zustand.bot, modified_gems, zustand
                )
                if new_route is None:
                    zustand.destination = gems_position
                else:
                    gem = new_route[2][0]
                    gems_position = modified_gems[gem - 1].position
                    zustand.destination = gems_position

        else:
            gem = route_for_us[2][0]
            gems_position = used_gems_our[gem - 1].position
            zustand.destination = gems_position


## setzt den Pfad zum ersten Gem in der Route


def set_path_to_gem(zustand: Zustand, used_gems):
    route_for_us = get_route_by_permutations_for_bot(zustand.bot, used_gems, zustand)

    gem = route_for_us[2][0]
    gems_position = used_gems[gem - 1].position
    if (
        zustand.approved_swarm_gem
        and zustand.approved_swarm_gem[1].position == gems_position
    ):
        redirect_swarm_gem_path(zustand, gems_position)
    else:
        zustand.destination = gems_position


def redirect_swarm_gem_path(zustand: Zustand, gem_position):
    if gem_position in zustand.gems_and_nodes:
        # Always take Node if needed
        taken_nodes = set()
        free_nodes = set()
        for node in zustand.gems_and_nodes[gem_position]:
            if (
                tuple(node)
                in zustand.teammates + list(zustand.opponents_on_nodes.keys())
                and tuple(node) != zustand.bot
            ):
                taken_nodes.add(tuple(node))
            else:
                free_nodes.add(tuple(node))

        if zustand.alarmed[0] and not any(
            bot == gem_position for bot in zustand.teammates if bot != zustand.bot
        ):
            zustand.destination = gem_position

        elif len(taken_nodes) < zustand.approved_swarm_gem[0] - 1:
            # if zustand.bot in taken_nodes:
            #    zustand.destination = zustand.bot
            #    return
            # dist_dicts = []
            # for teammate in zustand.teammates:
            #    dists_mate = bfs_distances_from(
            #        teammate,
            #        zustand,
            #        [tuple(n) for n in zustand.gems_and_nodes[gem_position]],
            #    )
            #    dists_mate = dict(
            #        sorted(dists_mate.items(), key=lambda item: (item[1]))
            #    )
            #    dist_dicts.append((teammate, dists_mate))

            # dist_dicts = sorted(
            #     dist_dicts, key=lambda x: (list(x[1].values())[0], x[0]), reverse=True
            # )

            # if zustand.approved_swarm_gem[0] == 3:
            #     dist_dicts.pop(0)

            # gem_collector = dist_dicts[0][0]

            # if zustand.bot == gem_collector:
            #    zustand.destination = gem_position
            #    return

            # owned_nodes = set()
            ##for teammate, dists in dist_dicts[1:]:
            #    taken_node = None
            #    for node in dists.keys():
            #        if node not in owned_nodes and node in free_nodes:
            #            owned_nodes.add(node)
            #            taken_node = node
            #            break

            #    if teammate == zustand.bot:
            #        if taken_node is not None:
            #            zustand.destination = taken_node
            #        else:
            #            zustand.destination = gem_position
            #        return

            # debug_print(dist_dicts, zustand)

            if zustand.bot in free_nodes:
                zustand.destination = zustand.bot
                debug_print("Stehe auf Node", zustand)
            else:
                dists = bfs_distances_from(gem_position, zustand, free_nodes)
                max_dist = 0
                best_node = None
                for node in free_nodes:
                    dist = dists[node]
                    if dist > max_dist:
                        max_dist = dist
                        best_node = node
                zustand.destination = best_node
        else:
            zustand.destination = gem_position
    else:
        zustand.destination = gem_position


def generate_permutations(zustand: Zustand):
    data = []
    if zustand.with_opponent == False:
        count = 5  # Länge der Permutationen
        max_gems = 5  # Anzahl der maximalen Zahlen
    else:
        count = 3  # Länge der Permutationen
        max_gems = 4  # Anzahl der maximalen Zahlen
    zustand.permutations = {}
    for i in range(zustand.config.max_gems):
        if i < max_gems:
            data.append(i + 1)
        if i + 1 == 1:
            zustand.permutations[i + 1] = [[1]]
            continue
        if i < count:
            length = i + 1
        else:
            length = count
        perms = list(permutations(data, length))
        zustand.permutations[i + 1] = perms
