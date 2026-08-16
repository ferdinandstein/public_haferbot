import heapq
import itertools
from collections import deque
import sys
from include.checks import check_if_path_blocked
from include.zustand import Zustand
from include.highlighting import debug_print
import random
from typing import List


def generate_a_star_path(zustand: Zustand, destination, origin):
    """Generiert einen Pfad von origin zu destination unter
    Berücksichtigung aller Kostenfaktoren (Wände, unbekannte Felder, Gegner).
    Gibt den Pfad zurück."""
    import time

    start_time = time.perf_counter_ns()

    COST_BASE = 20
    dst_x, dst_y = destination[0], destination[1]
    start_x, start_y = origin[0], origin[1]

    width = zustand.config.width
    height = zustand.config.height
    matrix = zustand.saved_matrix
    vis_radius = zustand.config.vis_radius

    g_costs = [[float("inf")] * width for _ in range(height)]
    g_costs[start_y][start_x] = 0
    visited_matrix = [[False] * width for _ in range(height)]
    parents = {(start_x, start_y): None}
    counter = itertools.count()

    # (g_cost, tie_breaker, counter, x, y, unknown_streak, last_move)
    open_heap = [(0, 0, next(counter), start_x, start_y, 0, 0)]

    move_dict_rev = {(1, 0): "E", (-1, 0): "W", (0, 1): "S", (0, -1): "N"}

    while open_heap:
        _, _, _, cx, cy, c_streak, move_to_it = heapq.heappop(open_heap)

        if visited_matrix[cy][cx]:
            continue
        visited_matrix[cy][cx] = True

        if cx == dst_x and cy == dst_y:
            # Zeitmessung und Rückgabe
            zustand.run_time_analyse.append(
                ["path_find", (time.perf_counter_ns() - start_time) / 1_000_000]
            )
            return reconstruct_path(cx, cy, parents, zustand)

        current_g = g_costs[cy][cx]

        for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]:
            nx, ny = cx + dx, cy + dy

            if not (0 <= nx < width and 0 <= ny < height):
                continue

            # 3. Kollisions Check
            cell_char = matrix[ny][nx]
            if cell_char == "X":
                continue

            if visited_matrix[ny][nx]:
                continue

            # --- KOSTENBERECHNUNG ---
            # Der Schritt kostet COST_BASE
            step_cost = COST_BASE

            # Risiko-Logik für unbekannte Felder
            is_unknown = cell_char == "/"
            new_streak = c_streak + 1 if is_unknown else 0
            if is_unknown:
                dist_from_start = current_g / COST_BASE
                risk_factor = (
                    zustand.weights.a_risk_factor_low
                    if dist_from_start < vis_radius
                    else zustand.weights.a_risk_factor_high
                )
                step_cost += (
                    3 + (new_streak * zustand.weights.a_streak_weigth)
                ) * risk_factor

            # Wandabstand am Zielort
            dist_to_wall = zustand.wall_distance_cache[ny][nx]

            step_cost += zustand.penaltys.get(dist_to_wall, 0)
            if is_unknown and dist_to_wall == 1:
                step_cost += zustand.weights.a_unknown_and_wall_penalty

            # Gegner-Check (Massive Strafe)
            if (nx, ny) in [o["position"] for o in zustand.opponents]:
                step_cost += zustand.weights.a_opponent_penalty * COST_BASE
            if (nx, ny) in zustand.teammates:
                step_cost += zustand.weights.a_opponent_penalty * COST_BASE

            if (
                len(zustand.approved_swarm_gem) > 0
                and (nx, ny) == zustand.approved_swarm_gem[1].position
            ):
                step_cost += 12 * COST_BASE

            if (nx, ny) in [
                g.position for g in zustand.gems_in_buffer if g.type_ == "regular"
            ]:
                step_cost -= 3 * COST_BASE
                if step_cost < 0:
                    step_cost = 0

            if (nx, ny) in zustand.opponents_on_nodes.keys():
                step_cost += 25 * COST_BASE

            temp_g_cost = current_g + step_cost

            if temp_g_cost < g_costs[ny][nx]:
                g_costs[ny][nx] = temp_g_cost
                parents[(nx, ny)] = (cx, cy)

                move = move_dict_rev.get((dx, dy))
                tiebreak_score = 0 if move_to_it == move else 100

                heapq.heappush(
                    open_heap,
                    (
                        temp_g_cost,
                        tiebreak_score,
                        next(counter),
                        nx,
                        ny,
                        new_streak,
                        move,
                    ),
                )

    return None


def update_wall_cache(zustand: Zustand, new_walls, max_dist=4):
    """
    Berechnet für jedes Feld auf der Map die Distanz zur nächsten Wand.
    Nutzt einen Multi-Source-BFS für maximale Performance.
    """
    import time

    if len(new_walls) == 0 and zustand.tick > 0:
        return

    start_time = time.perf_counter_ns()
    width = zustand.config.width
    height = zustand.config.height
    matrix = zustand.saved_matrix

    queue = deque()

    # 1. Initialisierung: Überall 'max_dist'
    if zustand.wall_distance_cache is None:
        zustand.wall_distance_cache = [[max_dist] * width for _ in range(height)]
        width = zustand.config.width
        height = zustand.config.height

        for y in range(height):
            for x in range(width):
                if y == 0 or y == height - 1 or x == 0 or x == width - 1:
                    zustand.wall_distance_cache[y][x] = 0
                    queue.append((x, y, 0))

    # 2. Alle Wände finden und als Startpunkte (Distanz 0) in die Queue werfen
    for x, y in new_walls:
        if matrix[y][x] == "X":
            zustand.wall_distance_cache[y][x] = 0
            queue.append((x, y, 0))

    # 3. Multi-Source BFS
    while queue:
        cx, cy, d = queue.popleft()

        if d >= max_dist:
            continue

        for dx, dy in [
            (0, 1),
            (0, -1),
            (1, 0),
            (-1, 0),
            (1, 1),
            (1, -1),
            (-1, 1),
            (-1, -1),
        ]:
            nx, ny = cx + dx, cy + dy

            # Bounds Check
            if 0 <= nx < width and 0 <= ny < height:
                # Wenn wir einen kürzeren Weg zu einer Wand gefunden haben:
                if zustand.wall_distance_cache[ny][nx] > d + 1:
                    zustand.wall_distance_cache[ny][nx] = d + 1
                    queue.append((nx, ny, d + 1))

    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1_000_000,
        ]
    )


def reconstruct_path(end_x, end_y, parents, zustand: Zustand):
    """
    Baut den Pfad aus dem Dictionary zurück und wandelt ihn
    am Ende wieder in Position-Objekte um (damit der Rest vom Code passt).
    """
    path = []
    curr = (end_x, end_y)
    zustand.test = []

    while curr is not None:
        path.append(curr)
        parent = parents[curr]
        curr = parent

    path.reverse()
    return path


def multi_source_a_star(
    origin: tuple,
    zustand: Zustand,
    targets: List[tuple],
):
    """
    Berechnet die Distanz (in Ticks) vom 'origin' zu ALLEN Zielen in der 'targets'-Liste gleichzeitig.
    Nutzt exakt dieselbe Kosten-Logik wie der A*-Pfadfinder.

    Returns:
        dict: {Position_Objekt: int_distanz_in_ticks, ...}
    """
    import time

    start_time = time.perf_counter_ns()

    # --- SETUP ---
    COST_BASE = 20
    width = zustand.config.width
    height = zustand.config.height
    matrix = zustand.saved_matrix
    vis_radius = zustand.config.vis_radius

    # Mapping: (x, y) -> Position-Objekt (damit wir das richtige Objekt zurückgeben können)
    # Wir filtern Ziele heraus, die auf Wänden liegen (unmöglich erreichbar)
    target_map = {}
    for t in targets:
        if 0 <= t[0] < width and 0 <= t[1] < height and matrix[t[1]][t[0]] != "X":
            target_map[(t[0], t[1])] = t

    # Wenn keine gültigen Ziele da sind, können wir uns die ganze Mühe sparen
    if not target_map:
        return {}

    start_x, start_y = origin[0], origin[1]

    # --- DATENSTRUKTUREN ---
    # Wir speichern nur die G-Kosten (Weighted Cost)
    g_costs = [[float("inf")] * width for _ in range(height)]
    g_costs[start_y][start_x] = 0

    visited_matrix = [[False] * width for _ in range(height)]

    # Heap: (weighted_cost, tiebreak_score, real_ticks, counter, x, y, unknown_streak, move)
    # real_ticks: Die tatsächliche Anzahl der Schritte
    counter = itertools.count()
    open_heap = [(0, 0, 0, next(counter), start_x, start_y, 0, None)]

    results = {}
    targets_remaining = len(target_map)

    directions = [(0, -1), (0, 1), (1, 0), (-1, 0)]
    move_dict_rev = {(1, 0): "E", (-1, 0): "W", (0, 1): "S", (0, -1): "N"}

    # --- HAUPTSCHLEIFE ---
    while open_heap:
        w_cost, _, ticks, _, cx, cy, c_streak, move_to_it = heapq.heappop(open_heap)

        if visited_matrix[cy][cx]:
            continue
        visited_matrix[cy][cx] = True

        # IST DIESER KNOTEN EIN ZIEL?
        if (cx, cy) in target_map:
            target_obj = target_map[(cx, cy)]
            # Wir speichern 'ticks'
            if target_obj not in results:
                results[target_obj] = ticks
                targets_remaining -= 1

                # Wenn wir alle Ziele gefunden haben -> Abbruch!
                if targets_remaining == 0:
                    break

        # --- NACHBARN ---
        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy

            # 1. Bounds & Wall Check
            if not (0 <= nx < width and 0 <= ny < height):
                continue

            cell_char = matrix[ny][nx]
            if cell_char == "X":
                continue

            if visited_matrix[ny][nx]:
                continue

            # --- KOSTEN-LOGIK (Identisch zum A*) ---
            step_penalty = 0
            is_unknown = cell_char == "/"

            new_streak = c_streak + 1 if is_unknown else 0

            if is_unknown:
                # Distanz basierend auf Ticks schätzen
                dist_from_start = ticks
                risk_factor = (
                    zustand.weights.a_risk_factor_low
                    if dist_from_start < vis_radius
                    else zustand.weights.a_risk_factor_high
                )
                step_penalty += (
                    3 + (new_streak * zustand.weights.a_streak_weigth)
                ) * risk_factor

            dist_to_wall = zustand.wall_distance_cache[ny][nx]
            step_penalty += zustand.penaltys.get(dist_to_wall, 0)

            if is_unknown and dist_to_wall == 1:
                step_penalty += zustand.weights.a_unknown_and_wall_penalty

            # Gegner-Check (Massive Strafe)
            if (nx, ny) in [
                o["position"] for o in zustand.opponents
            ] + zustand.teammates:
                step_penalty += zustand.weights.a_opponent_penalty * COST_BASE

            # Neue Kosten berechnen
            # Basiskosten pro Schritt (20) + Strafen
            new_w_cost = w_cost + COST_BASE + step_penalty
            new_ticks = ticks + 1

            # Update Heap
            if new_w_cost < g_costs[ny][nx]:
                move = move_dict_rev.get((dx, dy))
                tiebreak_score = 0 if move_to_it == move else 100

                g_costs[ny][nx] = new_w_cost
                heapq.heappush(
                    open_heap,
                    (
                        new_w_cost,
                        tiebreak_score,
                        new_ticks,
                        next(counter),
                        nx,
                        ny,
                        new_streak,
                        move,
                    ),
                )

    import inspect

    if (
        zustand.run_time_analyse
        and zustand.run_time_analyse[-1][0] == inspect.currentframe().f_code.co_name
    ):
        zustand.run_time_analyse[-1][1] += (
            time.perf_counter_ns() - start_time
        ) / 1_000_000
        zustand.run_time_analyse[-1][2] += 1
    else:
        zustand.run_time_analyse.append(
            [
                inspect.currentframe().f_code.co_name,
                (time.perf_counter_ns() - start_time) / 1_000_000,
                1,
            ]
        )

    return results


def bfs_distances_from(origin: tuple, zustand: Zustand, targets, walls=None):
    """
    BFS from origin to a list of target Positions. Returns a dict mapping Position -> distance (int) or None if unreachable.
    Stops early once all targets are found.
    """
    import time

    start_time = time.perf_counter_ns()

    width = zustand.config.width
    height = zustand.config.height
    saved = zustand.saved_matrix

    start = origin
    queue = deque([start])
    distances = {start: 0}

    targets_set = set(targets)
    found = {}

    if start in targets_set:
        found[start] = 0
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    # BFS main loop
    while queue:
        current = queue.popleft()
        x, y = current[0], current[1]
        distance = distances[current]

        if len(found) == len(targets_set):
            break

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue

            if saved[ny][nx] == "X":
                continue
            if walls is not None and (nx, ny) in walls:
                continue
            key = (nx, ny)
            if key in distances:
                continue
            neighbour_dist = distance + 1
            distances[key] = neighbour_dist
            if key in targets_set:
                found[key] = neighbour_dist
            queue.append(key)

    # Build result mapping only for requested targets
    result = {}
    for t in targets_set:
        result[t] = found.get(t)

    import inspect

    if (
        zustand.run_time_analyse
        and zustand.run_time_analyse[-1][0] == inspect.currentframe().f_code.co_name
    ):
        zustand.run_time_analyse[-1][1] += (
            time.perf_counter_ns() - start_time
        ) / 1_000_000
        zustand.run_time_analyse[-1][2] += 1
    else:
        zustand.run_time_analyse.append(
            [
                inspect.currentframe().f_code.co_name,
                (time.perf_counter_ns() - start_time) / 1_000_000,
                1,
            ]
        )
    return result


def get_fiel_nearest_to(origin: tuple, zustand: Zustand):
    """Finde das nächstgelegene freie Feld (Boden "0") von Origin aus"""
    width = zustand.config.width
    height = zustand.config.height

    queue = deque([origin])
    visited = set()
    visited.add(origin)

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while queue:

        field = queue.popleft()

        for dx, dy in directions:
            nx, ny = field[0] + dx, field[1] + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            pos_neighbour = (nx, ny)
            if pos_neighbour in visited:
                continue
            visited.add(pos_neighbour)

            if zustand.saved_matrix[ny][nx] == "0":  # Boden
                return (nx, ny)

            queue.append(pos_neighbour)


def nearest_to_field_of(zustand: Zustand, origin: tuple, destinations: List[tuple]):
    """Finde die Richtung, die uns am schnellsten zu einem der Ziele bringt."""
    width = zustand.config.width
    height = zustand.config.height

    queue = deque([origin])
    visited = set()
    visited.add(origin)

    while queue:
        field = queue.popleft()

        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = field[0] + dx, field[1] + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            pos_neighbour = (nx, ny)
            if pos_neighbour in visited:
                continue

            if pos_neighbour in destinations:
                return (nx, ny)

            if zustand.saved_matrix[ny][nx] != "X":  # Boden
                queue.append(pos_neighbour)

            visited.add(pos_neighbour)

    return None


def follow_a_star_path(zustand: Zustand):
    """Folgt dem A*-Pfad, weicht Gegnern aus und hat die 'Locked In' Logik."""
    if len(zustand.a_star_path) == 0:
        return "WAIT"

    position = zustand.a_star_path[0]

    # 1. Haben wir den nächsten Schritt erreicht?
    if zustand.bot == position:
        zustand.a_star_path.remove(position)
        if len(zustand.a_star_path) == 0:

            all_nodes = set()
            for set_of_nodes in zustand.gems_and_nodes.values():
                all_nodes.update(tuple(node) for node in set_of_nodes)

            if zustand.bot in all_nodes:
                # Ziel ist Node
                debug_print("Ziel ist Node, prüfe Nachbarn auf Teammates.", zustand)
                neighbour_dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
                random.shuffle(neighbour_dirs)  # Zufällige Reihenfolge für die Nachbarn
                for dx, dy in neighbour_dirs:
                    if (position[0] + dx, position[1] + dy) in zustand.teammates:
                        # Teammate ist neben an.
                        # Wir müssen von der Node runter.
                        if blocking_path_from_to(
                            zustand,
                            zustand.bot,
                            (position[0] + dx, position[1] + dy),
                            zustand.approved_swarm_gem[1].position,
                        ):
                            debug_print(
                                "Teammate ist nebenan, weiche aus, weil ich blockiere.",
                                zustand,
                            )
                            neighbours = []
                            for dx, dy in neighbour_dirs:
                                nx = zustand.bot[0] + dx
                                ny = zustand.bot[1] + dy

                                # Bounds check
                                if not (
                                    0 <= ny < zustand.config.height
                                    and 0 <= nx < zustand.config.width
                                ):
                                    continue

                                if (
                                    zustand.saved_matrix[ny][nx] != "X"
                                    and (nx, ny)
                                    not in [o["position"] for o in zustand.opponents]
                                    + zustand.teammates
                                ):
                                    neighbours.append((nx, ny))

                            if len(neighbours) > 0:
                                debug_print(
                                    f"Found valid neighbours. {neighbours}", zustand
                                )
                                nx, ny = nearest_to_field_of(
                                    zustand,
                                    zustand.approved_swarm_gem[1].position,
                                    neighbours,
                                )
                                debug_print(f"Nearest to gem is {(nx, ny)}", zustand)
                                offset = (nx - zustand.bot[0], ny - zustand.bot[1])
                                move_dict_rev = {
                                    (1, 0): "E",
                                    (-1, 0): "W",
                                    (0, 1): "S",
                                    (0, -1): "N",
                                }
                                return move_dict_rev[(offset[0], offset[1])]
                            else:
                                debug_print("No valid neighbours found.", zustand)
                                return "WAIT"
            return "WAIT"
        position = zustand.a_star_path[0]

    # 2. Ist der Gegner im Weg?
    if position in [o["position"] for o in zustand.opponents]:

        if len(zustand.a_star_path) > 5:
            destination = zustand.a_star_path[4]
        else:
            destination = zustand.a_star_path[-1]

        debug_print("#####Ausweichen", zustand)

        # Wir definieren alle möglichen Ausweich-Richtungen als Optionen
        evasion_options = [
            {"move": "E", "dx": 1, "dy": 0, "cond": destination[0] > zustand.bot[0]},
            {"move": "W", "dx": -1, "dy": 0, "cond": destination[0] < zustand.bot[0]},
            {"move": "S", "dx": 0, "dy": 1, "cond": destination[1] > zustand.bot[1]},
            {"move": "N", "dx": 0, "dy": -1, "cond": destination[1] < zustand.bot[1]},
        ]

        random.shuffle(evasion_options)

        for opt in evasion_options:
            if opt["cond"]:
                nx = zustand.bot[0] + opt["dx"]
                ny = zustand.bot[1] + opt["dy"]

                if (
                    zustand.saved_matrix[ny][nx] == "0"
                    and (nx, ny)
                    not in [o["position"] for o in zustand.opponents]
                    + zustand.teammates
                ):
                    # Neuen Pfad berechnen
                    zustand.a_star_path = generate_a_star_path(
                        zustand,
                        zustand.destination,
                        (nx, ny),
                    )
                    return opt["move"]

        # No alternative found, that is in the way of destination

        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        random.shuffle(dirs)

        move_dict_rev = {(1, 0): "E", (-1, 0): "W", (0, 1): "S", (0, -1): "N"}

        strong_opponents = [
            "🧠",
            "🍪",
            "🥷",
            "🍋",
            "🤘",
            "🦋",
            "🦉",
            "🐍",
            "🐣",
        ]

        backwards_going = True
        if (
            (zustand.opponent_emoji and zustand.opponent_emoji in strong_opponents)
            or zustand.my_points > zustand.opponent_points + zustand.weights.f_min_diff
        ):
            backwards_going = (
                False  # Bei starken Gegnern eher oder wenn vorne nicht zurückweichen
            )

        # Letzten Move bestimmen für "nicht umdrehen" Logik
        last_move_vec = (0, 0)
        move_vec_map = {
            "E": (1, 0),
            "W": (-1, 0),
            "S": (0, 1),
            "N": (0, -1),
            "WAIT": (0, 0),
        }
        if zustand.last_move in move_vec_map:
            last_move_vec = move_vec_map[zustand.last_move]

        for dx, dy in dirs:
            nx = zustand.bot[0] + dx
            ny = zustand.bot[1] + dy

            # Bounds check
            if not (
                0 <= ny < len(zustand.saved_matrix)
                and 0 <= nx < len(zustand.saved_matrix[0])
            ):
                continue

            if (
                zustand.saved_matrix[ny][nx] == "0"
                and (nx, ny)
                not in [o["position"] for o in zustand.opponents] + zustand.teammates
                and zustand.initative == True
            ):
                # Wenn wir nicht rückwärts gehen sollen, prüfen wir, ob dieser Move genau zurück führt
                if backwards_going == False and last_move_vec == (-dx, -dy):
                    continue

                # Pfad neu berechnen ab der Ausweich-Position
                zustand.a_star_path = generate_a_star_path(
                    zustand,
                    zustand.destination,
                    (nx, ny),
                )

                return move_dict_rev[(dx, dy)]

        return "WAIT"

    if position in zustand.teammates:
        if (zustand.teammates.index(position) + zustand.tick // 10) % 4 > (
            zustand.config.bot_id + zustand.tick // 10
        ) % 4:
            evasion_options = [
                {
                    "move": "E",
                    "dx": 1,
                    "dy": 0,
                },
                {
                    "move": "W",
                    "dx": -1,
                    "dy": 0,
                },
                {
                    "move": "S",
                    "dx": 0,
                    "dy": 1,
                },
                {
                    "move": "N",
                    "dx": 0,
                    "dy": -1,
                },
            ]
            random.shuffle(evasion_options)
            for opt in evasion_options:
                nx = zustand.bot[0] + opt["dx"]
                ny = zustand.bot[1] + opt["dy"]

                if (
                    zustand.saved_matrix[ny][nx] == "0"
                    and (nx, ny)
                    not in [o["position"] for o in zustand.opponents]
                    + zustand.teammates
                ):
                    # Neuen Pfad berechnen
                    zustand.a_star_path = generate_a_star_path(
                        zustand,
                        zustand.destination,
                        (nx, ny),
                    )
                    return opt["move"]
            return "WAIT"

    # 3. Standard-Bewegung (Wenn kein Gegner im Weg ist)
    if zustand.bot[0] < position[0]:
        return "E"
    elif zustand.bot[0] > position[0]:
        return "W"
    elif zustand.bot[1] < position[1]:
        return "S"
    elif zustand.bot[1] > position[1]:
        return "N"

    return "WAIT"


def blocking_path_from_to(zustand: Zustand, blocker, origin, destination):
    dist_without = bfs_distances_from(origin, zustand, [destination])[destination]
    dict_with = bfs_distances_from(origin, zustand, [destination], walls=[blocker])

    if dict_with is not None and dict_with.get(destination) is not None:

        if dist_without < dict_with.get(destination, 1000):
            return True
        return False
    return True


def get_fov(zustand: Zustand, origin: tuple):
    """Gibt zurück visible walkable und unknown tiles vom origin aus gesehen."""
    import time

    start_time = time.perf_counter_ns()

    saved = zustand.saved_matrix
    current = zustand.current_matrix
    rows = len(saved)
    cols = len(saved[0])

    visible_walkable = set()
    visible_unknown = set()

    def is_visible_till(p_x, p_y):
        """Prüfe Sichtlinie zwischen origin und p_x, p_y mit Bresenham-Linie.

        Verbesserungen:
        - Endpunkte werden innerhalb des gültigen Bereichs verwendet.
        - Eine Kachel blockiert die Sicht, wenn entweder `saved` oder `current` ein "X" hat.
        """
        # Check ob innerhalb der Grenzen
        p_x = max(0, min(cols - 1, p_x))
        p_y = max(0, min(rows - 1, p_y))

        dx = abs(p_x - origin[0])
        dy = abs(p_y - origin[1])

        x, y = origin[0], origin[1]

        x_inc = 1 if p_x > origin[0] else -1
        y_inc = 1 if p_y > origin[1] else -1
        error = dx - dy
        dx2 = dx * 2
        dy2 = dy * 2

        for _ in range(zustand.config.vis_radius + 2):
            # Stop, wenn außerhalb (sollte nicht passieren)
            if not (0 <= y < rows and 0 <= x < cols):
                break
            # Sicht wird durch bekannte Wände in entweder saved oder current geblockt
            if saved[y][x] == "X" or current[y][x] == "X":
                return
            if current[y][x] == "0":
                visible_walkable.add((x, y))
            elif current[y][x] == "/":
                visible_unknown.add((x, y))
            if x == p_x and y == p_y:
                return
            if error > 0:
                x += x_inc
                error -= dy2
            else:
                y += y_inc
                error += dx2

    # Für jedes Randteil wird die Linie gezogen (Endpoints clamped innerhalb von is_visible_till)
    for i in range(zustand.config.vis_radius * 2 + 1):
        y = origin[1] + (i - zustand.config.vis_radius)

        is_visible_till(origin[0] + zustand.config.vis_radius, y)
        is_visible_till(origin[0] - zustand.config.vis_radius, y)
        x = origin[0] + (i - zustand.config.vis_radius)

        is_visible_till(x, origin[1] + zustand.config.vis_radius)
        is_visible_till(x, origin[1] - zustand.config.vis_radius)

    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )
    return visible_walkable, visible_unknown


def get_all_distances_to_bot(zustand: Zustand):
    """
    Berechnet die Distanz (in Ticks) vom 'bot' zu ALLEN Feldern gleichzeitig.
    Nutzt exakt dieselbe Kosten-Logik wie der A*-Pfadfinder.
    Schließt außerdem unbekannte abgeschlossene Areas.

    Returns:
        dict: {Position_Objekt: int_distanz_in_ticks, ...}
    """
    import time

    start_time = time.perf_counter_ns()

    # --- SETUP ---
    COST_BASE = 20
    width = zustand.config.width
    height = zustand.config.height
    matrix = zustand.saved_matrix
    vis_radius = zustand.config.vis_radius

    start_x, start_y = zustand.bot[0], zustand.bot[1]

    # --- DATENSTRUKTUREN ---
    # Wir speichern nur die G-Kosten (Weighted Cost)
    g_costs_matrix = [[float("inf")] * width for _ in range(height)]
    g_costs_matrix[start_y][start_x] = 0
    tick_matrix = [[-1] * width for _ in range(height)]
    tick_matrix[start_y][start_x] = 0

    open_heap = [(0, 0, 0, start_x, start_y, 0, None)]

    visited_matrix = [[False] * width for _ in range(height)]

    directions = [(0, -1), (0, 1), (1, 0), (-1, 0)]
    move_dict_rev = {(1, 0): "E", (-1, 0): "W", (0, 1): "S", (0, -1): "N"}

    # --- HAUPTSCHLEIFE ---
    while open_heap:
        w_cost, _, ticks, cx, cy, c_streak, move_to_it = heapq.heappop(open_heap)

        # Lazy Deletion Check über Bool-Matrix (extrem schnell)
        if visited_matrix[cy][cx]:
            continue
        visited_matrix[cy][cx] = True

        # --- NACHBARN ---
        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy

            # 1. Bounds Check (inline)
            if not (0 <= nx < width and 0 <= ny < height):
                continue

            if visited_matrix[ny][nx]:
                continue

            cell_char = matrix[ny][nx]
            if cell_char == "X":
                continue

            # --- KOSTEN-LOGIK ---
            step_penalty = 0
            is_unknown = cell_char == "/"

            new_streak = c_streak + 1 if is_unknown else 0

            if is_unknown:
                risk_factor = (
                    zustand.weights.a_risk_factor_low
                    if ticks < vis_radius
                    else zustand.weights.a_risk_factor_high
                )
                step_penalty += (
                    3 + (new_streak * zustand.weights.a_streak_weigth)
                ) * risk_factor

            dist_to_wall = zustand.wall_distance_cache[ny][nx]

            step_penalty += zustand.penaltys.get(dist_to_wall, 0)

            if is_unknown and dist_to_wall == 1:
                step_penalty += zustand.weights.a_unknown_and_wall_penalty

            if (nx, ny) in [
                o["position"] for o in zustand.opponents
            ] + zustand.teammates:
                step_penalty += zustand.weights.a_opponent_penalty * COST_BASE

            new_w_cost = w_cost + COST_BASE + step_penalty

            # Array Zugriff statt Dict Lookup
            if new_w_cost < g_costs_matrix[ny][nx]:
                g_costs_matrix[ny][nx] = new_w_cost
                new_ticks = ticks + 1
                tick_matrix[ny][nx] = new_ticks

                move = move_dict_rev.get((dx, dy))
                if move_to_it == move:
                    tiebreak_score = 0
                else:
                    tiebreak_score = 100

                heapq.heappush(
                    open_heap,
                    (new_w_cost, tiebreak_score, new_ticks, nx, ny, new_streak, move),
                )

    final_distances = {}
    known_tiles = []
    zustand.unknown_tiles = set()

    for y in range(height):
        for x in range(width):
            cell = matrix[y][x]

            if cell == "/" and not visited_matrix[y][x]:
                zustand.saved_matrix[y][x] = "X"
                zustand.current_matrix[y][x] = "X"

            elif cell == "0":
                known_tiles.append([x, y])

            if cell == "/":
                zustand.unknown_tiles.add((x, y))

            ticks = tick_matrix[y][x]
            if ticks != -1:
                final_distances[(x, y)] = ticks

    zustand.known_tiles = known_tiles
    zustand.distances_to_bot = final_distances

    # Runtime Analyse
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1_000_000,
        ]
    )


def select_best_field_with_opponent(zustand: Zustand):
    """Findet das beste Feld, von wo aus der Bot am meisten erreicht unter berücksichtigung des Gegners"""
    ox, oy = zustand.opponent

    fields = [(ox, oy + 1), (ox, oy - 1), (ox + 1, oy), (ox - 1, oy)]

    width = zustand.config.width
    height = zustand.config.height
    best_diff = -100000
    best_field = None
    for field in fields:
        if not (0 <= field[0] < width and 0 <= field[1] < height):
            continue
        if zustand.saved_matrix[field[1]][field[0]] == "X":
            continue
        possesions = [[None] * width for _ in range(height)]
        possesions[field[1]][field[0]] = "bot"
        possesions[zustand.opponent[1]][zustand.opponent[0]] = "opponent"
        q = deque()
        q.append((field))
        q.append(zustand.opponent)
        bot_count = 0
        opponent_count = 0

        while q:
            x, y = q.popleft()
            possesion_current = possesions[y][x]
            for nx, ny in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
                if 0 <= nx < width and 0 <= ny < height:

                    if (zustand.saved_matrix[ny][nx] != "X") and possesions[ny][
                        nx
                    ] is None:
                        possesions[ny][nx] = possesion_current
                        if possesion_current == "bot":
                            bot_count += 1
                        else:
                            opponent_count += 1
                        q.append((nx, ny))

        if bot_count - opponent_count > best_diff:
            best_diff = bot_count - opponent_count
            best_field = field
    return best_field


def validate_path(zustand: Zustand, move: str):
    if zustand.a_star_path is not None and move in ["N", "S", "E", "W", "WAIT"]:
        if check_if_path_blocked(zustand):
            zustand.a_star_path = generate_a_star_path(
                zustand, zustand.destination, zustand.bot
            )
            move = follow_a_star_path(zustand)
    return move


def get_next_field(zustand: Zustand, move: str):
    move_vec_map = {
        "E": (1, 0),
        "W": (-1, 0),
        "S": (0, 1),
        "N": (0, -1),
        "WAIT": (0, 0),
    }
    if move in move_vec_map:
        dx, dy = move_vec_map[move]
        nx, ny = zustand.bot[0] + dx, zustand.bot[1] + dy
        if 0 <= nx < zustand.config.width and 0 <= ny < zustand.config.height:
            if (
                zustand.saved_matrix[ny][nx] != "X"
                and (nx, ny)
                not in [o["position"] for o in zustand.opponents] + zustand.teammates
            ):
                return (nx, ny)
    return zustand.bot
