from collections import deque

from include.highlighting import debug_print
from include.pathfinding_logics import follow_a_star_path, generate_a_star_path
from include.zustand import Zustand


def place_mid_portal(zustand: Zustand, position: tuple):
    id = len(zustand.mid_portals) + 1

    move_dict = {(0, -1): "N", (0, 1): "S", (1, 0): "E", (-1, 0): "W"}
    all_portals = []
    for portal in zustand.mid_portals:
        all_portals.append(portal[0])
    for portal in zustand.border_portals:
        all_portals.append(portal[0])

    if (
        zustand.saved_matrix[position[1]][position[0]] == "X"
        and (position[0], position[1]) not in all_portals
    ):
        dx = position[0] - zustand.bot[0]
        dy = position[1] - zustand.bot[1]
        quarter = move_dict[(dx, dy)]
        move = "P" + str(id) + quarter
        zustand.mid_portals.append([(position[0], position[1]), zustand.bot])
        return move


def get_nearest_portal_field_wall(zustand: Zustand, position: tuple):
    queue = deque([position])
    visited = set()
    visited.add(position)
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    all_portals = []
    for portal in zustand.mid_portals:
        all_portals.append(portal[0])
    for portal in zustand.border_portals:
        all_portals.append(portal[0])

    while queue:
        current = queue.popleft()

        for x, y in dirs:
            nx, ny = current[0] + x, current[1] + y
            if zustand.saved_matrix[ny][nx] == "X" and any(
                zustand.saved_matrix[ny + dy][nx + dx] == "0" for dx, dy in dirs
            ):
                if (nx, ny) not in all_portals:
                    return (nx, ny)

        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = current[0] + dx, current[1] + dy
            if 0 <= nx < zustand.config.width and 0 <= ny < zustand.config.height:
                if (nx, ny) not in visited and zustand.saved_matrix[ny][nx] != "X":
                    visited.add((nx, ny))
                    queue.append((nx, ny))

    return None


def go_to_or_place_midportal(zustand: Zustand):
    if zustand.best_portals is None:
        best_portals, score, dist_bot = evaluate_walls_for_portals(zustand)
    else:
        best_portals_new, score_new, dist_bot_new = evaluate_walls_for_portals(zustand)
        best_portals, score, dist_bot = zustand.best_portals
        if score_new < score and len(zustand.mid_portals) == 0:
            best_portals, score, dist_bot = best_portals_new, score_new, dist_bot_new
    debug_print(f"Best portals: {best_portals}, Score: {score}", zustand)

    if (
        (score < 100 and dist_bot < 7)
        or (zustand.tick > 10 or len(zustand.remembered_gems) > 0)
    ) and best_portals is not None:

        zustand.best_portals = (best_portals, score, dist_bot)
        free_portals = []
        for portal in best_portals:
            if portal not in [p[0] for p in zustand.mid_portals]:
                free_portals.append(portal)

        if len(free_portals) < 3:
            next_portal = get_nearest_portal_field_wall(zustand, zustand.bot)
        else:
            next_portal = None
            min_dist = float("inf")
            for portal in free_portals:
                dist = abs(zustand.bot[0] - portal[0]) + abs(zustand.bot[1] - portal[1])
                if dist < min_dist:
                    min_dist = dist
                    next_portal = portal

        neighbours = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = next_portal[0] + dx, next_portal[1] + dy
            if 0 <= nx < zustand.config.width and 0 <= ny < zustand.config.height:
                if zustand.saved_matrix[ny][nx] == "0" and (nx, ny) not in [
                    p[0] for p in zustand.mid_portals
                ]:
                    neighbours.append((nx, ny))

        if len(neighbours) == 0:
            raise ValueError(
                "No valid neighbours around the portal position!" + str(next_portal)
            )

        min_dist = float("inf")
        best_neighbour = None
        for p_start in neighbours:
            dist = sum(
                abs(p_start[0] - p[0]) + abs(p_start[1] - p[1]) for p in best_portals
            )
            if dist < min_dist:
                min_dist = dist
                best_neighbour = p_start

        if zustand.bot == best_neighbour:
            move = place_mid_portal(zustand, next_portal)
        else:
            zustand.destination = best_neighbour
            zustand.a_star_path = generate_a_star_path(
                zustand, zustand.destination, zustand.bot
            )
            move = follow_a_star_path(zustand)
    else:
        zustand.destination = get_nearest_unknown_field(zustand)
        zustand.a_star_path = generate_a_star_path(
            zustand, zustand.destination, zustand.bot
        )

        move = follow_a_star_path(zustand)
    return move


def get_nearest_unknown_field(zustand: Zustand):
    queue = deque([zustand.bot])
    visited = set()
    visited.add(zustand.bot)
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while queue:
        current = queue.popleft()

        if zustand.saved_matrix[current[1]][current[0]] == "/":
            return current

        for x, y in dirs:
            nx, ny = current[0] + x, current[1] + y
            if 0 <= nx < zustand.config.width and 0 <= ny < zustand.config.height:
                if (nx, ny) not in visited and zustand.saved_matrix[ny][nx] != "X":
                    visited.add((nx, ny))
                    queue.append((nx, ny))


def evaluate_walls_for_portals(zustand: Zustand):
    walls = []
    for x in range(zustand.config.width):
        for y in range(zustand.config.height):
            if zustand.saved_matrix[y][x] == "X":
                valid_neighbour = any(
                    0 <= x + ddx < zustand.config.width
                    and 0 <= y + ddy < zustand.config.height
                    and zustand.saved_matrix[y + ddy][x + ddx] == "0"
                    for ddx, ddy in [(0, 1), (0, -1), (1, 0), (-1, 0)]
                )
                if valid_neighbour:
                    walls.append((x, y))

    if len(walls) == 0:
        return None, 1000, 1000

    debug_print(f"Total walls: {len(walls)}", zustand)
    wall_clusters = []
    visited = set()
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]

    for start in walls:
        st = (start[0], start[1])
        if st in visited:
            continue

        # Neues Cluster beginnen
        queue = deque([st])
        cluster = []
        visited.add(st)

        while queue:
            current = queue.popleft()
            cluster.append(current)

            # Nachbarn durchsuchen
            x, y = current
            for dx, dy in dirs:
                nx, ny = x + dx, y + dy
                nt = (nx, ny)
                if nt in walls and nt not in visited:

                    visited.add(nt)
                    queue.append(nt)

        wall_clusters.append(cluster)

    wall_clusters = order_clusters(wall_clusters)

    possible_portal_combinations = []

    for cluster in wall_clusters:
        if len(cluster) < zustand.config.max_portals:
            continue

        for i in range(len(cluster) - 3):
            possible_portal_combinations.append(cluster[i : i + 4])

    if len(possible_portal_combinations) == 0:
        return None, 1000, 1000

    debug_print(f"Total Combos: {len(possible_portal_combinations)}", zustand)

    def sum_distances(combo):
        starts = []
        for portal in combo:
            possible_starts = []
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = portal[0] + dx, portal[1] + dy
                if (
                    0 <= nx < zustand.config.width
                    and 0 <= ny < zustand.config.height
                    and zustand.saved_matrix[ny][nx] == "0"
                ):
                    possible_starts.append((nx, ny))

            if len(possible_starts) == 0:
                raise ValueError(
                    "No possible start positions around portal: " + str(portal)
                )

            min_dist = float("inf")
            best_start = None
            for p_start in possible_starts:
                dist = sum(
                    abs(p_start[0] - p[0]) + abs(p_start[1] - p[1]) for p in combo
                )
                if dist < min_dist:
                    min_dist = dist
                    best_start = p_start

            starts.append(best_start)

        total_dist = 0
        for start in starts:
            total_dist += sum_bfs_dists(start, combo, zustand)

        dist_bot_to_starts = [zustand.distances_to_bot[s] for s in starts]
        min_dist_bot_to_start = min(dist_bot_to_starts)
        return total_dist, min_dist_bot_to_start

    portal_combos_with_scores = []
    for combo in possible_portal_combinations:
        score, dist_bot = sum_distances(combo)
        portal_combos_with_scores.append((combo, score, dist_bot))

    portal_combos_with_scores.sort(key=lambda x: (x[1], x[2]), reverse=True)

    best_combo = portal_combos_with_scores[-1]
    return best_combo


def order_clusters(clusters):
    # Sortiert Felder im Cluster nach Anfang bis Ende des Clusters
    ordered_clusters = []
    for cluster in clusters:
        start = cluster[0]
        for field in cluster:
            count = 0
            for x, y in [
                (0, 1),
                (0, -1),
                (1, 0),
                (-1, 0),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1),
            ]:
                nx, ny = field[0] + x, field[1] + y
                if (nx, ny) in cluster:
                    count += 1
                    start = field
            if count == 1:
                break

        ordered_cluster = []
        queue = deque([start])
        visited = set()
        visited.add(start)
        while queue:
            current = queue.popleft()
            ordered_cluster.append(current)
            for x, y in [
                (0, 1),
                (0, -1),
                (1, 0),
                (-1, 0),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1),
            ]:
                nx, ny = current[0] + x, current[1] + y
                if (nx, ny) in cluster and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny))
        ordered_clusters.append(ordered_cluster)
    return ordered_clusters


def sum_bfs_dists(start, portals, zustand):
    queue = deque([(start, 0)])
    visited = set()
    visited.add(start)
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    total_dist = 0
    found_portals = set()

    while queue:
        current, dist = queue.popleft()

        if current in portals and current not in found_portals:
            total_dist += dist
            found_portals.add(current)
            if len(found_portals) == len(portals):
                break

        for x, y in dirs:
            nx, ny = current[0] + x, current[1] + y
            if (
                0 <= nx < zustand.config.width
                and 0 <= ny < zustand.config.height
                and (nx, ny) not in visited
                and (zustand.saved_matrix[ny][nx] == "0" or (nx, ny) in portals)
            ):
                visited.add((nx, ny))
                queue.append(((nx, ny), dist + 1))

    return total_dist
