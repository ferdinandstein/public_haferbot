# Berechnet die beste Route zu den Edelsteinen
from collections import deque
import math
import statistics

from include.signal_interpreter import sort_gems_by_distance
from include.zustand import Zustand
from include.pathfinding_logics import (
    bfs_distances_from,
    follow_a_star_path,
    generate_a_star_path,
    multi_source_a_star,
    select_best_field_with_opponent,
)
from include.clustering import cluster_frontiers
from include.checks import check_for_change_gems
from include.matrix import (
    reset_matrix_floors,
    make_current_matrix,
    get_current_frontiers,
)
from include.mid import approximate_mid
from include.highlighting import debug_print
from itertools import permutations


def move_without_gem(zustand: Zustand):
    import time

    start_time = time.perf_counter_ns()
    cluster_frontiers(zustand)
    if zustand.frontiers == []:
        reset_matrix_floors(zustand)
        make_current_matrix(zustand)
        get_current_frontiers(zustand)
        cluster_frontiers(zustand)
        zustand.destination = zustand.clusters[0][1]
        zustand.a_star_path = generate_a_star_path(
            zustand, zustand.destination, zustand.bot
        )
    else:
        zustand.destination = zustand.clusters[0][1]
        zustand.a_star_path = generate_a_star_path(
            zustand, zustand.destination, zustand.bot
        )
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )


def set_path_to_mid(zustand: Zustand):
    if zustand.opponent is not None:
        zustand.destination = select_best_field_with_opponent(zustand)
    else:
        if zustand.mid_portals:
            zustand.mid = get_mid_by_mid_portals(zustand)
        elif len(zustand.saved_frontiers) > 0:
            zustand.mid = approximate_mid(zustand)
        elif midded == False:
            zustand.mid = approximate_mid(zustand)
            midded = True
        zustand.destination = zustand.mid
    zustand.a_star_path = generate_a_star_path(
        zustand, zustand.destination, zustand.bot
    )


def check_for_new_path(zustand: Zustand):
    if zustand.opponent is not None:
        get_path_with_opponent(zustand)
    else:
        used_gems = [
            gem
            for gem in (zustand.remembered_gems + zustand.hypothetical_gems)
            if gem.ttl - zustand.distances_to_bot.get(gem.position, 1000) >= 0
        ]
        used_gems.sort(
            key=lambda gem: sort_gems_by_distance(gem, zustand), reverse=True
        )
        if len(used_gems) == 0:
            if zustand.signal_level == 0:
                zustand.mid = approximate_mid(zustand)
                zustand.destination = zustand.mid
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

                evaluated_points = (
                    (gem_data["ttl"] - total_route_distance)
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
    zustand.destination = gems_position


def generate_permutations(zustand: Zustand):
    data = []
    if zustand.with_opponent == False:
        count = 7  # Länge der Permutationen
        max_gems = 7  # Anzahl der maximalen Zahlen
    else:
        count = 7  # Länge der Permutationen
        max_gems = 7  # Anzahl der maximalen Zahlen
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


def place_mid_portal(zustand: Zustand):
    """Platziert ein Mid-Portal auf einem angrenzenden Feld."""
    id_ = len(zustand.mid_portals) + 1
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    move_dict = {(0, -1): "N", (0, 1): "S", (1, 0): "E", (-1, 0): "W"}

    for dx, dy in dirs:
        nx = dx + zustand.bot[0]
        ny = dy + zustand.bot[1]
        if zustand.saved_matrix[ny][nx] == "X" and (nx, ny) not in zustand.any_portals:
            quarter = move_dict[(dx, dy)]
            move = "P" + str(id_) + quarter
            zustand.mid_portals.append([(nx, ny), zustand.bot])
            return move


def get_nearest_portal_field(zustand: Zustand, position: tuple):
    """Führt eine BFS durch, um das nächste freie Feld neben einer Wand zu finden, das nicht von einem Portal besetzt ist."""
    queue = deque([position])
    visited = set()
    visited.add(position)
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while queue:
        current = queue.popleft()

        for x, y in dirs:
            nx, ny = current[0] + x, current[1] + y
            if zustand.saved_matrix[ny][nx] == "X":
                if (nx, ny) not in zustand.any_portals:
                    return current

        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = current[0] + dx, current[1] + dy
            if 0 <= nx < zustand.config.width and 0 <= ny < zustand.config.height:
                if (nx, ny) not in visited and zustand.saved_matrix[ny][nx] != "X":
                    visited.add((nx, ny))
                    queue.append((nx, ny))

    return None


def go_to_or_place_midportal(zustand: Zustand):
    if len(zustand.mid_portals) > 0:
        pos = zustand.mid_portals[0][1]
    else:
        pos = zustand.bot
    nearest = get_nearest_portal_field(zustand, pos)
    if zustand.bot == nearest:
        move = place_mid_portal(zustand)
    else:
        zustand.destination = nearest
        zustand.a_star_path = generate_a_star_path(
            zustand, zustand.destination, zustand.bot
        )
        move = follow_a_star_path(zustand)
    return move


def get_dist_to_next_mid_portal(zustand: Zustand):

    nearest = get_nearest_portal_field(zustand, zustand.bot)
    dist = zustand.distances_to_bot[nearest]

    return dist


def count_fields_in_portal_range(zustand: Zustand, position: tuple):
    """Zählt Felder in Reichweite von 15, die nicht von einem Portal beansprucht werden."""
    queue = deque()
    visited = {}

    queue.append((position, 0, "pos"))
    visited[position] = "pos"

    portals = [portal[0] for portal in zustand.border_portals]
    for p in portals:
        if p not in visited:
            queue.append((p, 0, "portal"))
            visited[p] = "portal"

    claimed_score = 0

    while queue:
        if claimed_score > 1000:
            break
        curr_pos, dist, owner = queue.popleft()
        # if dist > 15:
        #    continue
        if owner == "pos":
            claimed_score += 1
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            next_pos = (curr_pos[0] + dx, curr_pos[1] + dy)
            if (
                0 <= next_pos[0] < zustand.config.width
                and 0 <= next_pos[1] < zustand.config.height
                and next_pos not in visited
                and zustand.saved_matrix[next_pos[1]][next_pos[0]] == "0"
            ):
                visited[next_pos] = owner
                queue.append((next_pos, dist + 1, owner))

    return claimed_score


def get_nearest_border_portal(zustand: Zustand):
    import time

    start_time = time.perf_counter_ns()
    if len(zustand.mid_portals) == 0:
        return None
    queue = deque([zustand.bot])
    visited = set()
    visited.add(zustand.bot)
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    all_entrances = []
    for portal in zustand.mid_portals:
        all_entrances.append(portal[1])

    for portal in zustand.border_portals:
        all_entrances.append(portal[1])

    i = 0

    while queue:
        if i > 15:
            return None
        current = queue.popleft()

        for x, y in dirs:
            nx, ny = current[0] + x, current[1] + y
            if zustand.saved_matrix[ny][nx] == "X":
                if (nx, ny) not in zustand.any_portals:
                    i += 1
                    dist_map = bfs_distances_from(current, zustand, all_entrances)
                    min_dist = min(dist_map.values())
                    claimed_fields = count_fields_in_portal_range(zustand, current)

                    if (
                        claimed_fields > zustand.weights.p_claimed_fields_min
                        and min_dist > zustand.weights.p_dist_min
                    ):
                        return current

        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = current[0] + dx, current[1] + dy
            if 0 <= nx < zustand.config.width and 0 <= ny < zustand.config.height:
                if (nx, ny) not in visited and zustand.saved_matrix[ny][nx] != "X":
                    visited.add((nx, ny))
                    queue.append((nx, ny))
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )


def place_border_portal(zustand: Zustand):
    """Platziert ein Border-Portal auf einem angrenzenden Feld."""
    id_ = len(zustand.border_portals) + 1
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    move_dict = {(0, -1): "N", (0, 1): "S", (1, 0): "E", (-1, 0): "W"}

    for dx, dy in dirs:
        nx = dx + zustand.bot[0]
        ny = dy + zustand.bot[1]
        if zustand.saved_matrix[ny][nx] == "X" and (nx, ny) not in zustand.any_portals:
            quarter = move_dict[(dx, dy)]
            move = "P" + str(id_) + quarter
            zustand.border_portals.append([(nx, ny), zustand.bot])
            return move


def get_mid_by_mid_portals(zustand: Zustand):
    """Berechnet die beste Mid-Position basierend auf den vorhandenen Mid-Portalen."""
    portals = [portal[0] for portal in zustand.mid_portals]
    candidates = []
    for portal in portals:
        for x in range(-2, 3):
            for y in range(-2, 3):
                candidate = (portal[0] + x, portal[1] + y)
                if (
                    0 <= candidate[0] < zustand.config.width
                    and 0 <= candidate[1] < zustand.config.height
                    and zustand.saved_matrix[candidate[1]][candidate[0]] == "0"
                ):
                    candidates.append(candidate)

    best_mid = None
    best_dist = float("inf")
    best_variance = float("inf")
    for candidate in candidates:
        dists = [abs(candidate[0] - p[0]) + abs(candidate[1] - p[1]) for p in portals]
        sum_dist = sum(dists)
        if sum_dist < best_dist:
            best_dist = sum_dist
            best_mid = candidate
            best_variance = statistics.variance(dists) if len(dists) > 1 else 0
        elif sum_dist == best_dist:
            variance = statistics.variance(dists) if len(dists) > 1 else 0
            if variance < best_variance:
                best_mid = candidate
                best_dist = sum_dist
                best_variance = variance

    return best_mid


def get_nearest_free_field(zustand: Zustand, start: tuple):
    """Führt eine BFS durch, um das nächste freie Feld zu finden."""
    queue = deque([start])
    visited = set()
    visited.add(start)
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while queue:
        current = queue.popleft()

        if zustand.saved_matrix[current[1]][current[0]] == "0":
            return current

        for x, y in dirs:
            nx, ny = current[0] + x, current[1] + y
            if 0 <= nx < zustand.config.width and 0 <= ny < zustand.config.height:
                if (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny))
    return None


def get_nearest_unknown_opponent_portal(zustand: Zustand):
    """Returns Best, dist, Nb"""
    min_dist = 1000
    best = None
    nb = None
    for portal in zustand.unknown_opponent_portals:
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = portal[0] + dx, portal[1] + dy
            if (
                0 <= nx < zustand.config.width
                and 0 <= ny < zustand.config.height
                and zustand.saved_matrix[ny][nx] == "0"
            ):
                dist = zustand.distances_to_bot[(nx, ny)]
                if dist < min_dist:
                    min_dist = dist
                    best = portal
                    nb = (nx, ny)

    return best, min_dist, nb


def go_to_unknown_opponent_portal(zustand: Zustand):
    best, min_dist, nb = get_nearest_unknown_opponent_portal(zustand)

    if min_dist == 0:
        offset = (-zustand.bot[0] + best[0], -zustand.bot[1] + best[1])
        move_dict = {(0, -1): "N", (0, 1): "S", (1, 0): "E", (-1, 0): "W"}
        move = move_dict[offset]
        zustand.went_through = True
    else:
        zustand.destination = nb
        zustand.a_star_path = generate_a_star_path(
            zustand, zustand.destination, zustand.bot
        )
        move = follow_a_star_path(zustand)

    return move
