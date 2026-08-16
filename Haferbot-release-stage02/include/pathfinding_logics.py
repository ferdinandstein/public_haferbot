import heapq
import itertools
from collections import deque
from include.zustand import Position, Zustand, Node
from include.highlighting import debug_print


def generate_a_star_path(zustand: Zustand, destination, origin):
    """
    Generiert einen Pfad vom aktuellen Bot-Standort zum Ziel (destination) mit dem A*-Algorithmus.
    Der Algorithmus arbeitet mit einer Prioritätswarteschlange (Heap), um immer den vielversprechendsten Knoten zu wählen.
    Die Kosten werden als f = g + h berechnet, wobei:
       g = bisherige Kosten vom Start
       h = Heuristik (geschätzte Entfernung zum Ziel)
    Die Funktion gibt eine Liste von Positionen zurück, die den Pfad vom Start zum Ziel darstellen.
    """
    import time

    start_time = time.perf_counter_ns()
    # --- KOSTEN-KONFIGURATION ---
    COST_BASE = 20
    # Strafen nach Abstand zur Wand:
    if len(zustand.remembered_gems) == zustand.config.max_gems:
        WALL_DIST_PENALTIES = {1: 2, 2: 1}
    else:
        WALL_DIST_PENALTIES = {1: 13, 2: 5, 3: 2}

    # Startknoten initialisieren
    start_node = Node()
    start_node.position = origin  # Startposition ist die aktuelle Bot-Position
    goal_node = destination  # Zielposition
    # Ein heapq Element hat alle Elemente innerhalb sortiert. Oben steht also immer das mit den niedrigsten f-Kosten
    # Priority queue (min-heap) für offene Knoten: (f_cost, counter, node)
    counter = itertools.count()  # Zähler für eindeutige Heap-Einträge
    open_heap = []  # Heap für offene Knoten
    open_dict = {}  # Dictionary: (x,y) -> bester Node im Open-Set
    closed_set = set()  # Menge der bereits besuchten Positionen

    # Kosten für den Startknoten setzen
    start_node.g_cost = 0  # Start hat keine Kosten
    # h_cost ist die Heuristik: Differenz zur Zielposition (siehe __sub__ in Position)
    start_node.h_cost = (start_node.position - goal_node) * COST_BASE
    start_node.f_cost = start_node.g_cost + start_node.h_cost
    start_node.parent = None  # Start hat keinen Vorgänger
    start_node.unknown_streak = 0

    start_pos = (start_node.position.x, start_node.position.y)
    open_dict[start_pos] = start_node
    heapq.heappush(
        open_heap, (start_node.f_cost, next(counter), start_node)
    )  # Fügt was hinzu

    # Hauptschleife: Solange noch offene Knoten existieren
    while open_heap:
        # Hole den Knoten mit den niedrigsten f-Kosten

        f_cost, _, first_node = heapq.heappop(
            open_heap
        )  # gibt das kleinste erste Element zurück
        current_nodes = [first_node]
        # alle weiteren mit gleichem f_cost holen
        while open_heap and open_heap[0][0] == f_cost:
            _, _, node = heapq.heappop(open_heap)
            current_nodes.append(node)
        best_wert = 10000
        # Node als current wählen, die am nächsten auf Achse ist.
        for node in current_nodes:
            dist_x = abs(node.position.x - destination.x)
            dist_y = abs(node.position.y - destination.y)
            least = min(dist_x, dist_y)
            if least < best_wert:
                current_node = node
                best_wert = least

        current_nodes.remove(current_node)

        for node in current_nodes:
            heapq.heappush(open_heap, (node.f_cost, next(counter), node))

        cur_pos = (current_node.position.x, current_node.position.y)

        # Überspringe veraltete Heap-Einträge
        if cur_pos in closed_set:
            continue

        # Ziel erreicht?
        if (
            current_node.position.x == goal_node.x
            and current_node.position.y == goal_node.y
        ):
            # Rekonstruiere und gib den Pfad zurück
            import inspect

            zustand.run_time_analyse.append(
                [
                    inspect.currentframe().f_code.co_name,
                    (time.perf_counter_ns() - start_time) / 1000000,
                ]
            )
            return reconstruct_path(current_node)
        # Markiere aktuelle Position als besucht
        closed_set.add(cur_pos)

        # Ermittle alle gültigen Nachbarn
        neighbours = get_neighbours_of_node(current_node, zustand)

        for neighbour in neighbours:
            npos = (neighbour.position.x, neighbour.position.y)
            if npos in closed_set:
                continue

            # --- DYNAMISCHE KOSTENBERECHNUNG ---
            step_cost = COST_BASE

            # 1. Unbekanntes Terrain
            is_unknown = zustand.saved_matrix[npos[1]][npos[0]] == "/"

            new_streak = current_node.unknown_streak + 1 if is_unknown else 0
            neighbour.unknown_streak = new_streak

            if is_unknown:
                dist_from_start = current_node.g_cost / COST_BASE

                # Wenn es nah ist (< Sichtradius), ist das Risiko klein, da wir es gleich sehen werden.
                risk_factor = 1  # Hier
                if dist_from_start < zustand.config.vis_radius:
                    # Geringes Risiko, wir klären das gleich auf
                    risk_factor *= 0.2
                else:
                    # Hohes Risiko
                    risk_factor *= 2.4

                # 2. Streak-Logik (Sackgassen-Vermeidung)
                penalty = (3 + (new_streak * 1.95)) * risk_factor  # Hier

                step_cost += penalty

            # 2. Abstand zur Wand prüfen
            dist_to_wall = get_distance_to_nearest_wall(
                npos[0], npos[1], zustand, max_dist=3
            )
            step_cost += WALL_DIST_PENALTIES.get(dist_to_wall, 0)

            if is_unknown and dist_to_wall == 1:  ##Hier
                step_cost += 4

            neighbour.h_cost = (neighbour.position - goal_node) * COST_BASE
            if neighbour.position == zustand.opponent:
                if (neighbour.h_cost / COST_BASE) + 2 > (start_node.h_cost / COST_BASE):
                    step_cost += 2 * COST_BASE
            # if (
            #    len(zustand.current_candidates) > 1
            #    and neighbour.h_cost > start_node.h_cost - 3 * COST_BASE
            # ):
            # signals = []
            # for candidate in zustand.current_candidates:
            #    dist = math.hypot(
            #        candidate.x - node.position.x, candidate.y - node.position.y
            #    )
            #    signal = 1 / (1 + (dist / zustand.config.signal_radius) ** 2)
            #    signals.append(round(signal, 10))

            # delta = round(statistics.pvariance(signals), 1)
            # step_cost -= int((delta) * 900)

            temporally_g_cost = current_node.g_cost + step_cost
            # ----------------------------------

            existing = open_dict.get(npos)
            # Falls der Nachbar noch nicht im Open-Set ist oder ein besserer Pfad gefunden wurde
            if existing is None or temporally_g_cost < existing.g_cost:
                # Setze den Vorgänger (für Pfadrekonstruktion)
                neighbour.parent = current_node
                neighbour.g_cost = temporally_g_cost

                neighbour.f_cost = neighbour.g_cost + neighbour.h_cost
                open_dict[npos] = neighbour
                heapq.heappush(open_heap, (neighbour.f_cost, next(counter), neighbour))
    # Kein Pfad gefunden
    return None


def get_distance_to_nearest_wall(x, y, zustand: Zustand, max_dist=3):
    """
    Scannt die Umgebung ab, um den Abstand zur nächsten Wand zu finden.
    Gibt 1 zurück, wenn die Wand direkt daneben ist, 2 bei einem Feld Lücke, etc.
    """
    for d in range(1, max_dist + 1):
        # Wir prüfen einen Ring/Quadrat um die aktuelle Position
        for dx in range(-d, d + 1):
            for dy in range(-d, d + 1):
                # Nur die Ränder des Quadrats prüfen (effizienter)
                if abs(dx) == d or abs(dy) == d:
                    nx, ny = x + dx, y + dy
                    if (
                        0 <= nx < zustand.config.width
                        and 0 <= ny < zustand.config.height
                    ):
                        if zustand.saved_matrix[ny][nx] == "X":
                            return d
    return max_dist + 1


def get_neighbours_of_node(current_node: Node, zustand: Zustand):

    # Gibt alle benachbarten freien Felder (Nodes) von einem Feld zurück.
    # Ein Feld ist frei, wenn in der Matrix an dieser Stelle "0" steht.
    # Es werden nur Felder innerhalb der Spielfeldgrenzen betrachtet.
    # Rückgabe: Liste von Node-Objekten für Norden, Süden, Osten, Westen (keine Diagonalen).

    neighbours = []

    x = current_node.position.x
    y = current_node.position.y
    width = zustand.config.width
    height = zustand.config.height

    # Norden
    if y - 1 >= 0 and (
        zustand.saved_matrix[y - 1][x] == "0"
        or zustand.saved_matrix[y - 1][x] == "/"
    ):
        neighbour = Node()
        neighbour.position = Position([x, y - 1])
        neighbours.append(neighbour)

    # Süden
    if y + 1 < height and (
        zustand.saved_matrix[y + 1][x] == "0"
        or zustand.saved_matrix[y + 1][x] == "/"
    ):
        neighbour = Node()
        neighbour.position = Position([x, y + 1])
        neighbours.append(neighbour)

    # Osten
    if x + 1 < width and (
        zustand.saved_matrix[y][x + 1] == "0"
        or zustand.saved_matrix[y][x + 1] == "/"
    ):
        neighbour = Node()
        neighbour.position = Position([x + 1, y])
        neighbours.append(neighbour)

    # Westen
    if x - 1 >= 0 and (
        zustand.saved_matrix[y][x - 1] == "0"
        or zustand.saved_matrix[y][x - 1] == "/"
    ):
        neighbour = Node()
        neighbour.position = Position([x - 1, y])
        neighbours.append(neighbour)

    return neighbours


def reconstruct_path(current_node):
    """
    Rekonstruiert den Pfad vom Ziel zum Start, indem die parent-Referenzen verfolgt werden.
    Gibt eine Liste von Positionen (vom Start bis zum Ziel) zurück.
    """
    path_positions = []
    node = current_node
    seen = set()  # Schutz vor Endlosschleifen
    while node is not None:
        pos = node.position
        key = (pos.x, pos.y)
        if key in seen:  # wenn wir schon mal bei der Position waren stimmt was nicht
            break
        seen.add(key)
        path_positions.append(pos)
        node = node.parent

    path_positions.reverse()  # Start -> Ziel
    return path_positions


def bfs_distances_from(origin: Position, zustand: Zustand, targets):
    """
    BFS from origin to a list of target Positions. Returns a dict mapping Position -> distance (int) or None if unreachable.
    Stops early once all targets are found.
    """

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
        x, y = current.x, current.y
        distance = distances[current]

        if len(found) == len(targets_set):
            break

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if saved[ny][nx] == "X":
                continue
            key = Position([nx, ny])
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
    return result


def get_fiel_nearest_to(origin: Position, zustand: Zustand):
    width = zustand.config.width
    height = zustand.config.height

    queue = deque([origin])
    visited = set()
    visited.add(origin)

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while queue:

        field = queue.popleft()

        for dx, dy in directions:
            nx, ny = field.x + dx, field.y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            pos_neighbour = Position([nx, ny])
            if pos_neighbour in visited:
                continue
            visited.add(pos_neighbour)

            if zustand.current_matrix[ny][nx] == "0":  # Boden
                return Position([nx, ny])

            queue.append(pos_neighbour)


# Funktion um dem Pfad zu folgen
def follow_a_star_path(zustand: Zustand):
    if len(zustand.a_star_path) == 0:
        return "WAIT"
    position = zustand.a_star_path[0]

    if zustand.bot.x == position.x and zustand.bot.y == position.y:
        # remove the reached node
        zustand.a_star_path.remove(position)
        # if path is now empty, nothing to do
        if len(zustand.a_star_path) == 0:
            return "WAIT"
        # otherwise continue towards the next position
        position = zustand.a_star_path[0]

    # other bot in the way
    if zustand.opponent is not None:
        if position == zustand.opponent:
            # look, if other direction is possible and useful
            # for path useful tiles, check if bot can go there
            if len(zustand.a_star_path) > 5:
                destination = zustand.a_star_path[4]
            else:
                destination = zustand.a_star_path[-1]
            debug_print("Ausweichen", zustand)
            if destination.x > zustand.bot.x:
                if (
                    zustand.saved_matrix[zustand.bot.y][zustand.bot.x + 1] == "0"
                    and zustand.opponent.x != zustand.bot.x + 1
                ):
                    zustand.a_star_path = generate_a_star_path(
                        zustand,
                        zustand.destination,
                        Position([zustand.bot.x + 1, zustand.bot.y]),
                    )
                    return "E"
            elif destination.x < zustand.bot.x:
                if (
                    zustand.saved_matrix[zustand.bot.y][zustand.bot.x - 1] == "0"
                    and zustand.opponent.x != zustand.bot.x - 1
                ):
                    zustand.a_star_path = generate_a_star_path(
                        zustand,
                        zustand.destination,
                        Position([zustand.bot.x - 1, zustand.bot.y]),
                    )
                    return "W"
            elif destination.y > zustand.bot.y:
                if (
                    zustand.saved_matrix[zustand.bot.y + 1][zustand.bot.x] == "0"
                    and zustand.opponent.y != zustand.bot.y + 1
                ):
                    zustand.a_star_path = generate_a_star_path(
                        zustand,
                        zustand.destination,
                        Position([zustand.bot.x, zustand.bot.y + 1]),
                    )
                    return "S"
            elif destination.y < zustand.bot.y:
                if (
                    zustand.saved_matrix[zustand.bot.y - 1][zustand.bot.x] == "0"
                    and zustand.opponent.y != zustand.bot.y - 1
                ):
                    zustand.a_star_path = generate_a_star_path(
                        zustand,
                        zustand.destination,
                        Position([zustand.bot.x, zustand.bot.y - 1]),
                    )
                    return "N"
            # No alternative found, that is in the way of destination

            # try to step aside, because opponent has larger FOV
            dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
            move_dict = {
                "E": (1, 0),
                "W": (-1, 0),
                "S": (0, 1),
                "N": (0, -1),
                "WAIT": (0, 0),
            }
            strong_opponents = [
                "🧠",
                "🍪",
                "☕",
                "🥷",
                "⛏",
                "🍋",
                "🤘",
                "💥",
                "🪲",
                "💎",
                "💀",
                "Ni",
                "🦋",
                "🗿",
                "🥵",
                "🦎",
                "🏹",
                "🐑",
            ]
            # Nur bei schlechten zurück gehen
            # bei guten warten
            if zustand.opponent_emoji and zustand.opponent_emoji in strong_opponents:
                backwards_going = False
            else:
                # bad Opponent
                backwards_going = True

            for dx, dy in dirs:
                nx = zustand.bot.x + dx
                ny = zustand.bot.y + dy
                if (
                    zustand.saved_matrix[ny][nx] == "0"
                    and Position([nx, ny]) != zustand.opponent
                ):
                    if backwards_going == False and move_dict[zustand.last_move] == (
                        -dx,
                        -dy,
                    ):
                        continue
                    # found alternative position to step aside
                    if dx == 1:
                        zustand.a_star_path = generate_a_star_path(
                            zustand,
                            zustand.destination,
                            Position([zustand.bot.x + dx, zustand.bot.y + dy]),
                        )
                        # reinsert current position
                        return "E"
                    elif dx == -1:
                        zustand.a_star_path = generate_a_star_path(
                            zustand,
                            zustand.destination,
                            Position([zustand.bot.x + dx, zustand.bot.y + dy]),
                        )
                        return "W"
                    elif dy == 1:
                        zustand.a_star_path = generate_a_star_path(
                            zustand,
                            zustand.destination,
                            Position([zustand.bot.x + dx, zustand.bot.y + dy]),
                        )
                        return "S"
                    elif dy == -1:
                        zustand.a_star_path = generate_a_star_path(
                            zustand,
                            zustand.destination,
                            Position([zustand.bot.x + dx, zustand.bot.y + dy]),
                        )
                        return "N"
            return "WAIT"

    # Move towards the next position
    if zustand.bot.x < position.x:
        return "E"
    elif zustand.bot.x > position.x:
        return "W"
    elif zustand.bot.y < position.y:
        return "S"
    elif zustand.bot.y > position.y:
        return "N"


def get_best_reachable_center(zustand: Zustand):
    import time

    start_time = time.perf_counter_ns()
    width, height = zustand.config.width, zustand.config.height

    def bfs_farthest_point(start: Position):
        distances = [[-1 for _ in range(width)] for _ in range(height)]
        distances[start.y][start.x] = 0
        queue = deque([start])
        farthest_node = start
        max_dist = 0
        # Speichere Vorgänger für die Pfadrückverfolgung
        parent = {(start): None}

        while queue:
            current = queue.popleft()

            if distances[current.y][current.x] > max_dist:
                max_dist = distances[current.y][current.x]
                farthest_node = current

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = current.x + dx, current.y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if zustand.saved_matrix[ny][nx] != "X" and distances[ny][nx] == -1:
                        distances[ny][nx] = distances[current.y][current.x] + 1
                        parent[Position([nx, ny])] = current
                        queue.append(Position([nx, ny]))
        return farthest_node, max_dist, parent

    # 1. Schritt: Starte beim Bot und finde den am weitesten entfernten Punkt (A)
    pos_A, _, _ = bfs_farthest_point(zustand.bot)

    # 2. Schritt: Starte bei A und finde den am weitesten entfernten Punkt (B)
    pos_B, dist_AB, parents = bfs_farthest_point(pos_A)

    # 3. Schritt: Den Pfad von B zurück nach A rekonstruieren
    path = []
    curr = pos_B
    while curr is not None:
        path.append(curr)
        curr = parents[curr]

    # 4. Schritt: Die Mitte dieses Pfades nehmen
    if not path:
        return None
    center_idx = len(path) // 2
    best = path[center_idx]
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )

    return best


def get_mid(zustand: Zustand):
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
        return Position([width // 2, height // 2])
    
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
    return Position([best_mid[0], best_mid[1]])

def get_field_nearest_mid(zustand: Zustand):
    width = zustand.config.width
    height = zustand.config.height
    mid = Position([width // 2, height//2])

    saved = zustand.saved_matrix
    visited = set()
    visited.add(mid)

    queue = deque([mid])

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    # BFS main loop
    while queue:
        current = queue.popleft()
        x, y = current.x, current.y

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if saved[ny][nx] != "X":
                return Position([nx, ny])
            key = Position([nx, ny])
            if key in visited:
                continue
            queue.append(key)


def get_fov(zustand: Zustand, origin: Position):
    """Gibt zurück visible walkable und unknown tiles vom origin aus gesehen."""
    import time

    start_time = time.perf_counter_ns()
    if zustand.dictionary_of_all_tiles[origin]["tiles"] != []:
        tiles = zustand.dictionary_of_all_tiles[origin]["tiles"]
        matrix = zustand.current_matrix

        visible_walkable = set()
        visible_unknown = set()

        for pos in tiles:
            cell = matrix[pos.y][pos.x]
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

        dx = abs(p_x - origin.x)
        dy = abs(p_y - origin.y)

        x, y = origin.x, origin.y

        n = dx + dy
        x_inc = 1 if p_x > origin.x else -1
        y_inc = 1 if p_y > origin.y else -1
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
        y = origin.y + (i - zustand.config.vis_radius)

        is_visible_till(origin.x + zustand.config.vis_radius, y)
        is_visible_till(origin.x - zustand.config.vis_radius, y)
        x = origin.x + (i - zustand.config.vis_radius)

        is_visible_till(x, origin.y + zustand.config.vis_radius)
        is_visible_till(x, origin.y - zustand.config.vis_radius)

    # Konvertiere Tupelmengen in Position-Objekte
    visible_walkable_positions = {Position([x, y]) for x, y in visible_walkable}
    visible_unknown_positions = {Position([x, y]) for x, y in visible_unknown}
    if zustand.saved_frontiers == []:
        all_tiles = visible_unknown_positions | visible_walkable_positions
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
    return visible_walkable_positions, visible_unknown_positions


def get_all_distances_to_bot(zustand: Zustand):
    """Berechnet und speichert die Distanzen von allen erreichbaren Feldern zum Bot."""
    width = zustand.config.width
    height = zustand.config.height
    import time

    start_time = time.perf_counter_ns()

    visited = set()
    visited.add(zustand.bot)

    queue = deque([zustand.bot])
    distances = {zustand.bot: 0}

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while queue:
        current = queue.popleft()
        x, y = current.x, current.y
        distance = distances[current]

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if zustand.saved_matrix[ny][nx] == "X":
                continue
            key = Position([nx, ny])
            if key in distances:
                continue
            neighbour_dist = distance + 1
            distances[key] = neighbour_dist
            queue.append(key)
            visited.add(key)

    zustand.known_tiles = []
    for y in range(height):
        for x in range(width):
            if zustand.saved_matrix[y][x] == "0":
                zustand.known_tiles.append([x, y])
            if zustand.saved_matrix[y][x] == "/":
                if Position([x, y]) not in visited:
                    zustand.saved_matrix[y][x] = "X"
                    zustand.current_matrix[y][x] = "X"

    zustand.distances_to_bot = distances
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )
