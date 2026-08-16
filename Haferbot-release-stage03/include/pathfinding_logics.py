import heapq
import itertools
from collections import deque
import sys
from include.zustand import Zustand
from include.highlighting import debug_print
import random
from typing import List, Tuple, Optional

INF = 100000


def generate_a_star_path(zustand: Zustand, destination, origin):
    import time

    start_time = time.perf_counter_ns()

    # --- SETUP & KONSTANTEN ---
    COST_BASE = 20
    dst_x, dst_y = destination[0], destination[1]
    start_x, start_y = origin[0], origin[1]

    width = zustand.config.width
    height = zustand.config.height
    matrix = zustand.saved_matrix
    vis_radius = zustand.config.vis_radius

    # --- DATENSTRUKTUREN ---
    # Wir speichern G-Kosten in einem 2d array für schnellen Zugriff: (x, y) -> g_cost
    g_costs = [[float("inf")] * width for _ in range(height)]
    g_costs[start_y][start_x] = 0

    visited_matrix = [[False] * width for _ in range(height)]

    # Parents für Rekonstruktion: (child_x, child_y) -> (parent_x, parent_y)
    parents = {(start_x, start_y): None}

    counter = itertools.count()

    # Initial Heuristik
    h_start = (abs(start_x - dst_x) + abs(start_y - dst_y)) * COST_BASE

    # Heap-Tupel Struktur:
    # (f_cost, tie_breaker_alignment, counter, x, y, unknown_streak, move_to_it)
    open_heap = [(h_start, 0, next(counter), start_x, start_y, 0, 0)]

    directions = [(0, -1), (0, 1), (1, 0), (-1, 0)]

    move_dict_rev = {(1, 0): "E", (-1, 0): "W", (0, 1): "S", (0, -1): "N"}

    # --- HAUPTSCHLEIFE ---
    while open_heap:
        _, _, _, cx, cy, c_streak, move_to_it = heapq.heappop(open_heap)

        # Check: Haben wir diesen Knoten schon günstiger abgearbeitet? (Lazy Deletion)
        if visited_matrix[cy][cx]:
            continue
        visited_matrix[cy][cx] = True

        # Ziel erreicht?
        if cx == dst_x and cy == dst_y:
            import inspect

            zustand.run_time_analyse.append(
                [
                    inspect.currentframe().f_code.co_name,
                    (time.perf_counter_ns() - start_time) / 1_000_000,
                ]
            )
            return reconstruct_path(cx, cy, parents)

        # Aktuelle G-Kosten
        current_g = g_costs[cy][cx]

        # --- NACHBARN (Inlined) ---
        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy

            # 1. Bounds Check
            if not (0 <= nx < width and 0 <= ny < height):
                continue

            # 2. Kollisions Check
            cell_char = matrix[ny][nx]
            if cell_char == "X":
                continue

            if visited_matrix[ny][nx]:
                continue

            # --- KOSTENBERECHNUNG ---
            step_cost = COST_BASE
            is_unknown = cell_char == "/"

            # Streak Logik
            new_streak = c_streak + 1 if is_unknown else 0

            if is_unknown:
                dist_from_start = current_g / COST_BASE

                # Risiko Berechnung
                if dist_from_start < vis_radius:
                    risk_factor = 0.2
                else:
                    risk_factor = 2.4

                penalty = (3 + (new_streak * 1.95)) * risk_factor
                step_cost += penalty

            # Wandabstand
            dist_to_wall = zustand.wall_distance_cache[ny][nx]
            step_cost += zustand.penaltys.get(dist_to_wall, 0)

            if is_unknown and dist_to_wall == 1:
                step_cost += 4

            # Gegner-Logik (Heuristik Check)
            # Manhattan Distanz inline berechnet
            h_cost = (abs(nx - dst_x) + abs(ny - dst_y)) * COST_BASE

            # Check Gegner Position (Optimierter Zugriff)
            if (
                zustand.opponent
                and nx == zustand.opponent[0]
                and ny == zustand.opponent[1]
            ):
                start_h = abs(start_x - dst_x) + abs(start_y - dst_y)
                if (h_cost / COST_BASE) + 2 > start_h:
                    step_cost += 2 * COST_BASE

            temp_g_cost = current_g + step_cost

            # --- UPDATE HEAP ---
            # Wenn wir einen besseren Weg zu (nx, ny) gefunden haben oder es neu ist
            if temp_g_cost < g_costs[ny][nx]:
                g_costs[ny][nx] = temp_g_cost
                parents[(nx, ny)] = (cx, cy)

                new_f = temp_g_cost + h_cost

                move = move_dict_rev[(dx, dy)]
                if move_to_it == move:
                    tiebreak_score = 0
                else:
                    tiebreak_score = 100

                heapq.heappush(
                    open_heap,
                    (new_f, tiebreak_score, next(counter), nx, ny, new_streak, move),
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

    # 1. Initialisierung: Überall 'max_dist' (als Standardwert für "weit weg")
    # Wir nehmen ein 2D-Array (Liste von Listen) für O(1) Zugriff per Index
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


def reconstruct_path(end_x, end_y, parents):
    """
    Baut den Pfad aus dem Dictionary zurück und wandelt ihn
    am Ende wieder in Position-Objekte um (damit der Rest vom Code passt).
    """
    path = []
    curr = (end_x, end_y)

    while curr is not None:
        # Hier erzeugen wir die Objekte erst ganz am Schluss und nur für den Pfad!
        path.append(curr)
        curr = parents[curr]

    path.reverse()
    return path


def multi_source_a_star(
    origin: tuple,
    zustand: Zustand,
    targets,
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

    # Wenn keine gültigen Ziele da sind, sofort raus
    if not target_map:
        return {}

    start_x, start_y = origin[0], origin[1]

    # --- DATENSTRUKTUREN ---
    # Wir speichern nur die G-Kosten (Weighted Cost)
    g_costs = [[float("inf")] * width for _ in range(height)]
    g_costs[start_y][start_x] = 0

    visited_matrix = [[False] * width for _ in range(height)]

    # Heap: (weighted_cost, tiebreak_score, real_ticks, counter, x, y, unknown_streak, move)
    # real_ticks: Die tatsächliche Anzahl der Schritte (wichtig für TTL/Score!)
    counter = itertools.count()
    open_heap = [(0, 0, 0, next(counter), start_x, start_y, 0, None)]

    results = {}
    targets_remaining = len(target_map)

    directions = [(0, -1), (0, 1), (1, 0), (-1, 0)]
    move_dict_rev = {(1, 0): "E", (-1, 0): "W", (0, 1): "S", (0, -1): "N"}

    # --- HAUPTSCHLEIFE ---
    while open_heap:
        w_cost, _, ticks, _, cx, cy, c_streak, move_to_it = heapq.heappop(open_heap)

        # Lazy Deletion Check
        if visited_matrix[cy][cx]:
            continue
        visited_matrix[cy][cx] = True

        # IST DIESER KNOTEN EIN ZIEL?
        if (cx, cy) in target_map:
            target_obj = target_map[(cx, cy)]
            # Wir speichern die 'ticks' (echte Zeit), nicht die 'w_cost' (interne Bewertung)
            if target_obj not in results:
                results[target_obj] = ticks
                targets_remaining -= 1

                # Wenn wir alle Ziele gefunden haben -> Abbruch!
                if targets_remaining == 0:
                    break

        # Maximale Suchtiefe begrenzen (optional, für Performance)
        # Wenn wir schon 100 Schritte weg sind, lohnt es sich meist eh nicht mehr

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
                risk_factor = 0.2 if dist_from_start < vis_radius else 2.4
                step_penalty += (3 + (new_streak * 1.95)) * risk_factor

            dist_to_wall = zustand.wall_distance_cache[ny][nx]

            step_penalty += zustand.penaltys.get(dist_to_wall, 0)

            if is_unknown and dist_to_wall == 1:
                step_penalty += 4

            # Gegner-Check (Massive Strafe)
            if (
                zustand.opponent
                and nx == zustand.opponent[0]
                and ny == zustand.opponent[1]
            ):
                step_penalty += 2 * COST_BASE

            # Neue Kosten berechnen
            # Basiskosten pro Schritt (20) + Strafen
            new_w_cost = w_cost + COST_BASE + step_penalty
            new_ticks = ticks + 1

            # Update Heap
            if new_w_cost < g_costs[ny][nx]:
                move = move_dict_rev[(dx, dy)]
                if move_to_it == move:
                    tiebreak_score = 0
                else:
                    tiebreak_score = 100
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

    # Debugging / Profiling
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


def bfs_distances_from(origin: tuple, zustand: Zustand, targets):
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

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )
    return result


def get_fiel_nearest_to(origin: tuple, zustand: Zustand):
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

            if zustand.current_matrix[ny][nx] == "0":  # Boden
                return (nx, ny)

            queue.append(pos_neighbour)


# Funktion um dem Pfad zu folgen
def follow_a_star_path(zustand: Zustand):
    zustand.locked = False
    if len(zustand.a_star_path) == 0:
        return "WAIT"

    position = zustand.a_star_path[0]

    # 1. Haben wir den nächsten Schritt erreicht?
    if zustand.bot[0] == position[0] and zustand.bot[1] == position[1]:
        zustand.a_star_path.remove(position)
        if len(zustand.a_star_path) == 0:
            return "WAIT"
        position = zustand.a_star_path[0]

    if zustand.opponent:
        count = get_fields_for_opponent(zustand)
        if count < 30 and zustand.my_points > zustand.opponent_points + 1400:
            if zustand.locked == False:
                print(
                    f"Tja {zustand.opponent_emoji} Du wurdest leider eingesperrt!",
                    file=sys.stderr,
                    flush=True,
                )
                zustand.locked_in = zustand.tick
            elif zustand.locked_in + 20 == zustand.tick and zustand.locked == True:
                print(
                    f"Du solltest langsam mal locked in gehen, damit du noch gewinnst. Sonst wird das nichts!",
                    file=sys.stderr,
                    flush=True,
                )
            elif zustand.locked_in + 30 == zustand.tick and zustand.locked == True:
                print(
                    f"Achso, du bist ja schon locked in 😂",
                    file=sys.stderr,
                    flush=True,
                )
            elif (
                zustand.tick == zustand.config.max_ticks - 1 and zustand.locked == True
            ):
                print(
                    "Es tut mir leid, das ich unfair gespielt habe 😔. Aber: ",
                    file=sys.stderr,
                    flush=True,
                )
            zustand.locked = True
            return "WAIT"
        else:
            zustand.locked = False

    # 2. Ist der Gegner im Weg?
    if zustand.opponent is not None and position == zustand.opponent:

        if len(zustand.a_star_path) > 5:
            destination = zustand.a_star_path[4]
        else:
            destination = zustand.a_star_path[-1]

        debug_print("Ausweichen", zustand)

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

                if zustand.saved_matrix[ny][nx] == "0" and (
                    zustand.opponent[0] != nx or zustand.opponent[1] != ny
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
            zustand.opponent_emoji and zustand.opponent_emoji in strong_opponents
        ) or zustand.my_points > zustand.opponent_points + 1500:
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
                and (nx, ny) != zustand.opponent
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

    # 3. Standard-Bewegung (Wenn kein Gegner im Weg ist)
    # Hier muss nichts zufällig sein, da A* den besten Weg vorgibt.
    if zustand.bot[0] < position[0]:
        return "E"
    elif zustand.bot[0] > position[0]:
        return "W"
    elif zustand.bot[1] < position[1]:
        return "S"
    elif zustand.bot[1] > position[1]:
        return "N"

    return "WAIT"


def get_fields_for_opponent(zustand: Zustand):
    if zustand.opponent is None:
        return 10000
    else:
        queue = deque([zustand.opponent])
        count = 0
        visited = set(zustand.opponent)

        while queue:
            current = queue.popleft()
            if count > 30:
                break

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = current[0] + dx, current[1] + dy

                if 0 <= nx < zustand.config.width and 0 <= ny < zustand.config.height:
                    if (nx, ny) not in visited and zustand.saved_matrix[ny][nx] != "X":
                        if (nx, ny) != zustand.bot:
                            visited.add((nx, ny))
                            queue.append((nx, ny))
                            count += 1

        return count


def neighbors(x: int, y: int, height: int, width: int):
    """Yield orthogonale Nachbarn im (x,y)-Format."""
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= ny < height and 0 <= nx < width:
            yield (nx, ny)


def bfs(saved_matrix: List[List[str]], start: Tuple[int, int]) -> List[List[int]]:
    """
    BFS auf dem Gitter ab Start.
    start ist (x,y). dist wird als dist[y][x] gehalten.
    """
    H = len(saved_matrix)
    W = len(saved_matrix[0])
    sx, sy = start
    dist = [[INF] * W for _ in range(H)]
    q = deque()
    dist[sy][sx] = 0
    q.append((sx, sy))
    while q:
        x, y = q.popleft()
        d = dist[y][x]
        for nx, ny in neighbors(x, y, H, W):
            if saved_matrix[ny][nx] != "X" and dist[ny][nx] == INF:
                dist[ny][nx] = d + 1
                q.append((nx, ny))
    return dist


def find_any_free(saved_matrix: List[List[str]]) -> Optional[Tuple[int, int]]:
    H = len(saved_matrix)
    W = len(saved_matrix[0])
    for y in range(H):
        for x in range(W):
            if saved_matrix[y][x] != "X":
                return (x, y)
    return None


def choose_anchors(
    saved_matrix: List[List[str]],
    start_pos: Optional[Tuple[int, int]] = None,
    k: int = 5,
) -> List[Tuple[int, int]]:
    """
    Greedy farthest-sampling, arbeitet mit (x,y)-Tupeln.
    Gibt eine Liste von anchors als (x,y) zurück.
    """
    H = len(saved_matrix)
    W = len(saved_matrix[0])
    # Kandidaten in (x,y)-Form
    candidates = [
        (x, y) for y in range(H) for x in range(W) if saved_matrix[y][x] != "X"
    ]

    # Erster Anchor: start_pos (falls gültig) sonst erste freie Zelle
    if start_pos is None:
        start = find_any_free(saved_matrix)
    else:
        start = start_pos

    anchors: List[Tuple[int, int]] = [start]
    # cache die Distanz-Map des ersten Anchors
    first_dm = bfs(saved_matrix, start)
    dist_maps = [first_dm]

    # min_dists[y][x] = minimale Distanz zu irgendeinem bereits gewählten Anchor
    # kopiere first_dm (deep copy)
    min_dists = [row[:] for row in first_dm]

    while len(anchors) < k:
        best_cell = None
        best_min_dist = -1
        # wähle Kandidat mit maximalem min_dists
        for x, y in candidates:
            d = min_dists[y][x]
            if d > best_min_dist:
                best_min_dist = d
                best_cell = (x, y)
        if best_cell is None:
            break
        anchors.append(best_cell)
        new_dm = bfs(saved_matrix, best_cell)
        dist_maps.append(new_dm)
        # update min_dists mit neuen Distanzen
        for yy in range(H):
            row_min = min_dists[yy]
            new_row = new_dm[yy]
            for xx in range(W):
                if new_row[xx] < row_min[xx]:
                    row_min[xx] = new_row[xx]

    return anchors


def compute_anchor_weights(saved_matrix, anchors, dist_maps, unknown_scale=0.5):
    """
    anchors: List[(x,y)]
    dist_maps: List of 2D dist arrays dm[y][x] corresponding to anchors
    unknown_scale: Gewichtsfaktor für unknown ("/") gegenüber known ("0")
    Returns: List[float] normalized weights summing to 1 (one weight per anchor)
    """
    H = len(saved_matrix)
    W = len(saved_matrix[0])
    k = len(anchors)
    if k == 0:
        return []

    known_count = [0] * k
    unknown_count = [0] * k

    # Targets: nur Felder, die relevant sind (bekannt oder unbekannt)
    targets = [(x, y) for y in range(H) for x in range(W) if saved_matrix[y][x] != "X"]

    for x, y in targets:
        best_idx = None
        best_d = INF + 1
        for i, dm in enumerate(dist_maps):
            d = dm[y][x]
            if d < best_d:
                best_d = d
                best_idx = i
        # falls Target von allen Anchors unerreichbar ist, skippen
        if best_idx is None or best_d >= INF:
            continue
        if saved_matrix[y][x] == "0":
            known_count[best_idx] += 1
        else:
            unknown_count[best_idx] += 1

    # Rohgewichte: known zählt 1, unknown zählt unknown_scale
    raw = [known_count[i] + unknown_scale * unknown_count[i] for i in range(k)]
    s = sum(raw)
    if s == 0:
        # Fallback: gleiche Gewichte
        return [1.0 / k] * k
    return [r / s for r in raw]


def compute_score_map_from_anchors_weighted(
    saved_matrix: List[List[str]],
    dist_maps: List[List[List[int]]],
    anchor_weights: List[float],
) -> List[List[float]]:
    """
    Wie compute_score_map_from_anchors, aber mit vorgegebenen anchor_weights.
    Ergebnis ist ein float-Score pro Feld (kleiner = besser).
    """
    H = len(saved_matrix)
    W = len(saved_matrix[0])
    score = [[INF] * W for _ in range(H)]
    k = len(dist_maps)
    assert k == len(anchor_weights)

    for y in range(H):
        for x in range(W):
            if saved_matrix[y][x] == "X":
                continue
            s = 0.0
            unreachable = False
            for dm, w in zip(dist_maps, anchor_weights):
                dv = dm[y][x]
                if dv >= INF:
                    unreachable = True
                    break
                s += dv * w
            score[y][x] = INF if unreachable else s
    return score


def approximate_mid(zustand: Zustand) -> Tuple[int, int]:
    """
    Verwende die korrigierte choose_anchors:
    - anchors als (x,y) zurück
    - berechne dist_maps danach
    - wähle Feld mit minimalem Score
    """
    import time, inspect

    start_time = time.perf_counter_ns()

    H = len(zustand.saved_matrix)
    W = len(zustand.saved_matrix[0])

    # Ziele als (x,y)

    anchors = choose_anchors(zustand.saved_matrix, start_pos=None, k=5)

    # dist_maps berechnen (BFS pro Anchor)
    dist_maps = [bfs(zustand.saved_matrix, a) for a in anchors]

    # anchor-gewichte berechnen (unknown_scale z.B. 0.3)
    anchor_weights = compute_anchor_weights(
        zustand.saved_matrix, anchors, dist_maps, unknown_scale=0.7
    )

    # score_map mit gewichten
    score_map = compute_score_map_from_anchors_weighted(
        zustand.saved_matrix, dist_maps, anchor_weights
    )

    # 4) argmin (liefert (x,y))
    best = None
    bestscore = INF
    for y in range(H):
        for x in range(W):
            sc = score_map[y][x]
            if sc < bestscore:
                bestscore = sc
                best = (x, y)

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1_000_000,
        ]
    )

    return best


def get_mid(zustand: Zustand):
    import time

    start_time = time.perf_counter_ns()
    width = zustand.config.width
    height = zustand.config.height
    max_calls = 2
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def get_sum_of_all_distances(start_node, limit_sum):
        queue = deque([start_node])
        visited = {start_node}  # Set für O(1) Lookup
        total_sum = 0
        current_dist = 0

        # BFS in Layern (Ebenen), spart das Speichern der Distanz pro Knoten
        while queue:
            # Wenn wir das Limit überschreiten, sofort raus (Pruning)
            if total_sum > limit_sum:
                return float("inf")

            # Alle Knoten dieser Ebene abarbeiten
            for _ in range(len(queue)):
                cx, cy = queue.popleft()

                # Nachbarn prüfen
                for dx, dy in directions:
                    nx, ny = cx + dx, cy + dy

                    if 0 <= nx < width and 0 <= ny < height:
                        if (nx, ny) not in visited:
                            # Matrix Check
                            if zustand.saved_matrix[ny][nx] != "X":
                                visited.add((nx, ny))
                                queue.append((nx, ny))
                                total_sum += current_dist + 1

            current_dist += 1

        return total_sum

    best_sum = 100000
    calls = 0
    sum_x = 0
    sum_y = 0

    # Sammle alle bekannten Felder
    known_fields = zustand.known_tiles

    if not known_fields:
        return (width // 2, height // 2)

    count = len(known_fields)
    for p in known_fields:
        sum_x += p[0]
        sum_y += p[1]

    avg_x = sum_x / count
    avg_y = sum_y / count

    def dist_to_center(p):
        return abs(p[0] - avg_x) + abs(p[1] - avg_y)

    candidates = heapq.nsmallest(max_calls, known_fields, key=dist_to_center)
    avg_x = width / 2
    avg_y = height / 2
    candidates += heapq.nsmallest(max_calls, known_fields, key=dist_to_center)

    best_mid = candidates[0]

    for point in candidates:
        sum_distances = get_sum_of_all_distances((point[0], point[1]), best_sum)
        calls += 1
        # Nur speichern wenn besser als bisheriges Beste
        if sum_distances < best_sum:
            best_sum = sum_distances
            best_mid = point

    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )
    return (best_mid[0], best_mid[1])


def get_field_nearest_mid(zustand: Zustand):
    width = zustand.config.width
    height = zustand.config.height
    mid = (width // 2, height // 2)

    saved = zustand.saved_matrix
    visited = set()
    visited.add(mid)

    queue = deque([mid])

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    # BFS main loop
    while queue:
        current = queue.popleft()
        x, y = current[0], current[1]

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if saved[ny][nx] != "X":
                return (nx, ny)
            key = (nx, ny)
            if key in visited:
                continue
            queue.append(key)


def get_fov(zustand: Zustand, origin: tuple):
    """Gibt zurück visible walkable und unknown tiles vom origin aus gesehen."""
    import time

    start_time = time.perf_counter_ns()
    if zustand.dictionary_of_all_tiles[origin]["tiles"] != []:
        tiles = zustand.dictionary_of_all_tiles[origin]["tiles"]
        matrix = zustand.current_matrix

        visible_walkable = set()
        visible_unknown = set()

        for pos in tiles:
            cell = matrix[pos[1]][pos[0]]
            if cell == "0":
                visible_walkable.add(pos)
            elif cell == "/":
                visible_unknown.add(pos)

        return visible_walkable, visible_unknown
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

        n = dx + dy
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
        return

    # Für jedes Randteil wird die Linie gezogen (Endpoints clamped innerhalb von is_visible_till)
    for i in range(zustand.config.vis_radius * 2 + 1):
        y = origin[1] + (i - zustand.config.vis_radius)

        is_visible_till(origin[0] + zustand.config.vis_radius, y)
        is_visible_till(origin[0] - zustand.config.vis_radius, y)
        x = origin[0] + (i - zustand.config.vis_radius)

        is_visible_till(x, origin[1] + zustand.config.vis_radius)
        is_visible_till(x, origin[1] - zustand.config.vis_radius)

    # Konvertiere Tupelmengen in Position-Objekte
    if zustand.saved_frontiers == []:
        all_tiles = visible_unknown | visible_walkable
        zustand.dictionary_of_all_tiles[origin].update(
            {
                "tiles": all_tiles,
                "count": len(all_tiles),
                "LST": zustand.dictionary_of_all_tiles[origin]["LST"],
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
                risk_factor = 0.2 if ticks < vis_radius else 2.4
                step_penalty += (3 + (new_streak * 1.95)) * risk_factor

            dist_to_wall = zustand.wall_distance_cache[ny][nx]

            step_penalty += zustand.penaltys.get(dist_to_wall, 0)

            if is_unknown and dist_to_wall == 1:
                step_penalty += 4

            if (
                zustand.opponent
                and nx == zustand.opponent[0]
                and ny == zustand.opponent[1]
            ):
                step_penalty += 40  # 2 * COST_BASE

            new_w_cost = w_cost + COST_BASE + step_penalty

            # Array Zugriff statt Dict Lookup
            if new_w_cost < g_costs_matrix[ny][nx]:
                g_costs_matrix[ny][nx] = new_w_cost
                new_ticks = ticks + 1
                tick_matrix[ny][nx] = new_ticks

                move = move_dict_rev[(dx, dy)]
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
    stayed = zustand.opponent == zustand.last_opponent
    ox, oy = zustand.opponent

    if stayed:
        fields = [(ox, oy + 1), (ox, oy - 1), (ox + 1, oy), (ox - 1, oy)]
    else:
        fields = [
            (ox, oy + 2),
            (ox, oy - 2),
            (ox + 2, oy),
            (ox - 2, oy),
            (ox + 1, oy + 1),
            (ox - 1, oy - 1),
            (ox + 1, oy - 1),
            (ox - 1, oy + 1),
        ]

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
                    if (
                        zustand.saved_matrix[ny][nx] != "X"
                        and possesions[ny][nx] is None
                    ):
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
