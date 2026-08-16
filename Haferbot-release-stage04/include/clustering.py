from include.zustand import Zustand
from collections import deque
import math
from include.pathfinding_logics import (
    bfs_distances_from,
    get_field_nearest_mid,
    get_fov,
    get_mid,
)


def cluster_frontiers(zustand: Zustand):
    import time

    start_time = time.perf_counter_ns()
    clusters = []
    visited = set()

    # Alle möglichen Richtungen
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (-1, -1), (1, -1)]

    # Frontier als set
    frontier_set = set((p[0], p[1]) for p in zustand.frontiers)

    for start in zustand.frontiers:
        st = (start[0], start[1])
        if st in visited:
            continue

        # Neues Cluster beginnen
        queue = deque([st])
        cluster = []
        visited.add(st)

        while queue:
            current = queue.popleft()  # Tupel
            cluster.append(current)

            # Nachbarn durchsuchen
            x, y = current
            for dr, dc in dirs:
                nr, nc = x + dr, y + dc
                nt = (nr, nc)
                if nt in frontier_set and nt not in visited:
                    visited.add(nt)
                    queue.append(nt)

        clusters.append(cluster)

    clusters_with_mid = get_mid_for_each_cluster(zustand, clusters)
    zustand.clusters = clusters_with_mid
    assign_unknowns_to_frontiers(zustand)

    mids = []
    for cluster in clusters_with_mid:
        mids.append(cluster[1])

    # Einmalig: Anzahl Tiles je Owner (cluster id) berechnen
    cluster_tile_counts = {}
    cluster_sum_ages = {}
    cluster_sum_dist = {}
    cluster_real_tile_count = {}

    for info in zustand.dictionary_of_all_tiles.values():
        owner = info.get("owner")
        if owner is None:
            continue
        dist = info.get("dist", 0.01)
        age = zustand.tick - info.get("LST", zustand.tick)

        best_age = 200

        def get_value_for_age(age):
            value = (-1 / (math.pow(best_age, 2))) * (math.pow(age - best_age, 2)) + 1
            return value

        #
        cluster_real_tile_count[owner] = cluster_real_tile_count.get(owner, 0) + 1
        if zustand.tick > 10:
            if get_value_for_age(age + dist) < 0.1:
                continue

        cluster_sum_dist[owner] = cluster_sum_dist.get(owner, 0) + dist

        cluster_sum_ages[owner] = cluster_sum_ages.get(owner, 0) + age

        cluster_tile_counts[owner] = cluster_tile_counts.get(owner, 0) + 1

    # Map cluster object -> index, damit wir nicht .index() auf der Liste aufrufen müssen
    cluster_index_map = {id(cwm): idx for idx, cwm in enumerate(clusters_with_mid)}

    def sort_by_path_length_and_points(cluster_with_mid_of_cluster):
        # Cluster-ID per Map (schnell)
        idx = cluster_index_map.get(id(cluster_with_mid_of_cluster))
        tiles_of_cluster = cluster_tile_counts.get(idx, 0)
        sum_ages_of_cluster = cluster_sum_ages.get(idx, 0)
        real_tiles_of_cluster = cluster_real_tile_count.get(idx, 0)
        cluster_sum_distances = cluster_sum_dist.get(idx, 0)
        used_tile_count = tiles_of_cluster

        if used_tile_count == 0:
            if real_tiles_of_cluster != 0:
                used_tile_count = real_tiles_of_cluster
            else:
                return -1000

        if cluster_sum_distances == 0:
            cluster_sum_distances = 50

        if zustand.with_opponent == True:
            tile_weight = 1
            dist_weight = 3.875
            age_weight = 0.6875
            cluster_and_total_weight = 2.09375
            w1 = -0.0625
            w2 = 4.25
            w3 = 4.0625
            w4 = 3.875
            w5 = 1.0625
        else:
            tile_weight = 2
            dist_weight = 4
            age_weight = 5
            cluster_and_total_weight = 2
            w1 = 0.3
            w2 = 0.3
            w3 = 0.3
            w4 = 0.3
            w5 = 0.3
        total_cluster_dist_weight = 4
        tile_weight_cluster_score = 3

        cluster_tiles_points = (used_tile_count * tile_weight_cluster_score) / (
            (cluster_sum_distances / used_tile_count) * dist_weight
        ) + (get_value_for_age(sum_ages_of_cluster / used_tile_count)) * age_weight

        mid = cluster_with_mid_of_cluster[1]
        _, visible_unknown = get_fov(zustand, mid)

        distance = zustand.distances_to_bot[mid]

        # if zustand.signal_level == 0:
        #    return tiles_of_cluster * 3 - dist_to_mid - distance

        unknown_tiles = len(visible_unknown)
        sum_age = 0

        for tile in visible_unknown:
            sum_age += zustand.tick - zustand.dictionary_of_all_tiles[tile]["LST"]
        avg_age = sum_age / len(visible_unknown) if len(visible_unknown) > 0 else 0

        max_gems = zustand.config.max_gems
        spawn_rate_multiplier = 1 + ((zustand.config.gem_spawn_rate - 0.05) * 30)

        if max_gems == 1:
            total_points = (
                avg_age * (w1 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * total_cluster_dist_weight
            )
        elif max_gems == 2:
            total_points = (
                avg_age * (w2 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * total_cluster_dist_weight
            )
        elif max_gems == 3:
            total_points = (
                avg_age * (w3 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * total_cluster_dist_weight
            )
        elif max_gems == 4:
            total_points = (
                avg_age * (w4 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * total_cluster_dist_weight
            )
        else:
            total_points = (
                avg_age * (w5 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * total_cluster_dist_weight
            )
        return cluster_tiles_points * cluster_and_total_weight + total_points

    start_time_inner = time.perf_counter_ns()
    clusters_with_mid.sort(key=sort_by_path_length_and_points, reverse=True)
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name + "_inner",
            (time.perf_counter_ns() - start_time_inner) / 1000000,
        ]
    )

    # Die Cluster weden anhand ihres Besten Fronier Feldes sortiert, nach sichtbaren unbekannten Feldern und Distanz und noch mehr. Am Anfang von sorierter Liste bester Cluster
    zustand.clusters = clusters_with_mid


def get_mid_for_each_cluster(zustand: Zustand, clusters):
    """'Für jedes Cluster wird der Frontier mit der Sicht auf möglichst viele unbekannte (/) Felder ausgewählt."""
    clusters_with_mid = []
    import time

    start_time = time.perf_counter_ns()
    if zustand.with_opponent == True:
        for cluster in clusters:
            anzahl_frontiers = len(cluster)
            sum_x = 0
            sum_y = 0
            for frontier in cluster:
                sum_x += frontier[0]
                sum_y += frontier[1]
            avg_x = sum_x / anzahl_frontiers
            avg_y = sum_y / anzahl_frontiers
            avg_position = (int(avg_x), int(avg_y))
            best_delta = 1000
            best_pos = cluster[0]
            for frontier in cluster:
                if frontier == avg_position:
                    avg_position = frontier
                    break
                else:
                    dx = abs(frontier[0] - avg_position[0])
                    dy = abs(frontier[1] - avg_position[1])
                    if dx + dy < best_delta:
                        best_delta = dx + dy
                        best_pos = frontier
            clusters_with_mid.append((cluster, best_pos))
    else:
        for cluster in clusters:
            best_view = 0
            best_frontier = cluster[0]
            for frontier in cluster:
                _, view = get_fov(zustand, frontier)
                if len(view) > best_view:
                    best_view = len(view)
                    best_frontier = frontier

            clusters_with_mid.append((cluster, best_frontier))

    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )
    return clusters_with_mid


def actualize_dict(zustand: Zustand):
    import time

    start_time = time.perf_counter_ns()

    for tile in zustand.floors:
        if zustand.dictionary_of_all_tiles[tile]["LST"] != zustand.tick:
            zustand.dictionary_of_all_tiles[tile].update(
                {
                    "tiles": zustand.dictionary_of_all_tiles[tile]["tiles"],
                    "count": len(zustand.dictionary_of_all_tiles[tile]["tiles"]),
                    "LST": zustand.tick,
                    "owner": None,
                    "dist": None,
                }
            )  # LST = last seen tick

    if zustand.opponent is not None:
        walkable, unknown = get_fov(zustand, zustand.opponent)
        opponent_fov = list(walkable) + list(unknown)
        for tile in opponent_fov:
            if zustand.dictionary_of_all_tiles[tile]["LST"] != zustand.tick:
                zustand.dictionary_of_all_tiles[tile].update(
                    {
                        "tiles": zustand.dictionary_of_all_tiles[tile]["tiles"],
                        "count": len(zustand.dictionary_of_all_tiles[tile]["tiles"]),
                        "LST": zustand.tick,
                        "owner": None,
                        "dist": None,
                    }
                )  # LST = last seen tick

    if zustand.bot in zustand.dictionary_of_all_tiles:
        return
    # Sichtfeld des Bots speichern
    tiles = zustand.floors
    count = len(tiles)
    zustand.dictionary_of_all_tiles[zustand.bot].update(
        {
            "tiles": tiles,
            "count": count,
            "LST": zustand.tick,
            "owner": None,
            "dist": None,
        }
    )
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )


def assign_unknowns_to_frontiers(zustand: Zustand):
    width = zustand.config.width
    height = zustand.config.height
    import time

    start_time = time.perf_counter_ns()

    queue = deque()
    for tile in zustand.dictionary_of_all_tiles.values():
        tile["owner"] = None
        tile["dist"] = None

    for frontier_id, cluster in enumerate(zustand.clusters):
        mid = cluster[1]
        dist_mid = zustand.distances_to_bot[mid]
        zustand.dictionary_of_all_tiles[mid]["owner"] = frontier_id
        zustand.dictionary_of_all_tiles[mid]["dist"] = dist_mid
        queue.append(mid)
        for frontier in cluster[0]:
            zustand.dictionary_of_all_tiles[frontier]["owner"] = frontier_id
            zustand.dictionary_of_all_tiles[frontier]["dist"] = dist_mid
            queue.append(frontier)

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    # BFS um unbekannte Felder den Frontiers zuzuordnen
    i = 0

    while queue:

        field = queue.popleft()

        for dx, dy in directions:
            nx, ny = field[0] + dx, field[1] + dy
            pos_neighbour = (nx, ny)

            if not (0 <= nx < width and 0 <= ny < height):
                continue

            if zustand.current_matrix[ny][nx] == "0":  # Boden
                continue
            if zustand.current_matrix[ny][nx] == "X":  # Wand
                continue

            if zustand.dictionary_of_all_tiles[pos_neighbour]["owner"] is None:
                zustand.dictionary_of_all_tiles[pos_neighbour]["owner"] = (
                    zustand.dictionary_of_all_tiles[field]["owner"]
                )
                zustand.dictionary_of_all_tiles[pos_neighbour]["dist"] = (
                    zustand.dictionary_of_all_tiles[field]["dist"] + 1
                )
                queue.append(pos_neighbour)

        i += 1
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )
