# Berechnug des Feldes, was am zentralsten ist.
# Wird nicht genutzt, da in der aktuellen Stage immer ein Gem irgendwo unbemerkt sein kann

from collections import deque
import heapq
from typing import List, Tuple, Optional

from include.zustand import Zustand

INF = 100000


def bfs(
    saved_matrix: List[List[str]], start: Tuple[int, int], zustand: Zustand
) -> List[List[int]]:
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
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if (
                0 <= ny < H
                and 0 <= nx < W
                and saved_matrix[ny][nx] != "X"
                and dist[ny][nx] == INF
            ):
                dist[ny][nx] = d + 1
                q.append((nx, ny))
    return dist


def find_any_free(saved_matrix: List[List[str]]) -> Optional[Tuple[int, int]]:
    H = len(saved_matrix)
    W = len(saved_matrix[0])
    for y in range(H):
        for x in range(W):
            if saved_matrix[y][x] == "0":
                return (x, y)
    return None


def choose_anchors(
    saved_matrix: List[List[str]],
    zustand: Zustand,
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
    first_dm = bfs(saved_matrix, start, zustand)
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
        new_dm = bfs(saved_matrix, best_cell, zustand)
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

    anchors = choose_anchors(zustand.saved_matrix, zustand, start_pos=None, k=5)

    # dist_maps berechnen (BFS pro Anchor)
    dist_maps = [bfs(zustand.saved_matrix, a, zustand) for a in anchors]

    # anchor-gewichte berechnen (unknown_scale z.B. 0.3)
    anchor_weights = compute_anchor_weights(
        zustand.saved_matrix,
        anchors,
        dist_maps,
        unknown_scale=zustand.weights.m_unknown_scale,
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
    """Finde das Feld, von dem aus die Summe der Distanzen zu allen bekannten Feldern minimal ist."""
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
