from bisect import bisect_left, bisect_right
from collections import deque
import random
from include.zustand import Antenna, Zustand, Gem
import math
import numpy as np

from include.highlighting import debug_print


def calculate_signal(dist, zustand: Zustand):
    """Berechnet die Signalstärke für eine gegebene Distanz."""
    return 1 / (1 + (dist / zustand.config.signal_radius) ** 2)


def calculate_dist_squared_by_strength(strength, zustand: Zustand):
    """Berechnet die Distanz für eine gegebene Signalstärke."""
    if strength <= 0:
        return float("inf")

    dist_squared = zustand.config.signal_radius**2 * (1 / strength - 1)
    return dist_squared


def get_signal_from_known_gems(zustand: Zustand, pos: tuple):
    known_signal = 0
    for gem in zustand.remembered_gems:
        dist = math.hypot(pos[0] - gem.position[0], pos[1] - gem.position[1])
        age = zustand.config.gem_ttl - gem.ttl
        fade_multiplier = get_fade_by_tick(zustand, (zustand.tick - age))
        signal = calculate_signal(dist, zustand) * fade_multiplier
        known_signal += signal
    return known_signal


def get_candidates_for_signal(
    zustand: Zustand, signal_min, signal_max, antenna_position
):
    """
    Berechnet mögliche Positionen basierend auf dem Restsignal.
    """
    candidates_tuples = set()
    width = zustand.config.width
    height = zustand.config.height
    # tuple set damit es schneller ist
    floors = zustand.floors

    keys = list(zustand.signal_offsets.keys())
    idx_start = bisect_left(keys, signal_min)
    idx_end = bisect_right(keys, signal_max)
    ax = antenna_position[0]
    ay = antenna_position[1]

    for i in range(idx_start, idx_end):
        current_signal = keys[i]
        offsets = zustand.signal_offsets[current_signal]
        # 4 Quadranten berücksichtigen
        for dx, dy in offsets:
            # Symmetrie-Punkte generieren
            for nx, ny in (
                (ax + dx, ay + dy),
                (ax + dx, ay - dy),
                (ax - dx, ay + dy),
                (ax - dx, ay - dy),
            ):

                # Bounds Check
                if 0 < nx < width and 0 < ny < height:
                    if zustand.saved_matrix[ny][nx] == "X":
                        continue

                    if (nx, ny) in floors:
                        continue

                    candidates_tuples.add((nx, ny))
    candidates = candidates_tuples
    return candidates


def get_fade_by_tick(zustand: Zustand, tick):
    age = zustand.tick - tick
    fade_multiplier = 1
    signal_fade = zustand.config.signal_fade
    if age < signal_fade:
        fade_multiplier = (age + 1) / signal_fade
    elif age >= zustand.config.gem_ttl - signal_fade:
        fade_multiplier = (zustand.config.gem_ttl - age) / signal_fade

    if fade_multiplier <= 0:
        fade_multiplier = 1000
    if fade_multiplier > 1:
        fade_multiplier = 1
    return fade_multiplier


def sort_gems_by_distance(gem: Gem, zustand: Zustand):

    dist = zustand.distances_to_bot[gem.position]
    if dist > 0:
        res = 1 / dist
    else:
        res = 10000

    return res


def calculate_gems_for_signals(zustand: Zustand):
    import time

    start_time = time.perf_counter_ns()

    zustand.hypothetical_gems = []
    zustand.candidates_by_antenna = []
    all_pos_signal = zustand.antennas.copy()

    all_pos_signal.append(Antenna(zustand.bot, zustand.signal_level))
    no_signal = True
    for antenna in all_pos_signal:
        if antenna.signal > 0:
            no_signal = False
            break
    if (
        no_signal
        or zustand.signal_level - get_signal_from_known_gems(zustand, zustand.bot)
        <= 0.04
    ):
        return
    zustand.spawn_ticks[1] == -1
    if zustand.spawn_ticks[0] == -1:
        zustand.spawn_ticks[0] = zustand.tick

    fade_multiplier = get_fade_by_tick(zustand, zustand.spawn_ticks[0])

    circles = []
    for antenna in all_pos_signal:
        known_signal = get_signal_from_known_gems(zustand, antenna.position)

        real_signal_min = max(
            0,
            (
                ((antenna.signal - known_signal) - zustand.error_margin)
                / fade_multiplier
            ),
        )
        real_signal_max = min(
            1,
            (
                ((antenna.signal - known_signal) + zustand.error_margin)
                / fade_multiplier
            ),
        )
        dist_max_sq = calculate_dist_squared_by_strength(real_signal_min, zustand)
        dist_min_sq = calculate_dist_squared_by_strength(real_signal_max, zustand)
        circles.append(
            (antenna.position[0], antenna.position[1], dist_min_sq, dist_max_sq)
        )

    valid_points = get_valid_fields_in_circles(zustand, circles)
    y_coords, x_coords = np.where(valid_points)
    candidates = set(zip(x_coords.tolist(), y_coords.tolist()))

    if len(zustand.candidates[0]) > 0:
        candidates = candidates.intersection(zustand.candidates[0])

    # debug_print(f"Valid candidates: {len(candidates)}", zustand)

    if len(candidates) == 0:
        get_possible_pairs(zustand)
        zustand.candidates[0] = set()
        return

    zustand.candidates[0] = candidates

    if len(candidates) == 1:
        zustand.remembered_gems.append(Gem(list(candidates.pop()), 280))
        zustand.candidates[0] = set()
        return

    best_pos = None
    best_dist = float("inf")
    if candidates:
        for candidate in candidates:
            dist = zustand.distances_to_bot.get(candidate, float("inf"))
            if dist < best_dist:
                best_dist = dist
                best_pos = candidate
        if not best_pos:
            return

        zustand.hypothetical_gems.append(Gem(list(best_pos), 280))

    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )


def get_possible_pairs(
    zustand: Zustand,
) -> list[tuple[tuple[int, int], set[tuple[int, int]]]]:
    """
    Versucht, zwei Gems zu lokalisieren, indem wir annehmen, dass einer davon
    aus der Liste candidates_gem_A stammt.

    Returns: Eine Liste von Tupeln: [ (PosA1, [PosB_Candidates]), (PosA2, [PosB_Candidates]), ... ]
    """
    import time

    start_time = time.perf_counter_ns()
    candidates_gem_a = None

    for i in range(1, 8):
        if zustand.dictionary_of_signals_and_stuff.get(zustand.tick - i) is not None:

            if (
                len(
                    zustand.dictionary_of_signals_and_stuff[zustand.tick - i][
                        "candidates"
                    ][0]
                )
                > 0
            ):
                candidates_gem_a = zustand.dictionary_of_signals_and_stuff[
                    zustand.tick - i
                ]["candidates"][0]

    possible_pairs = []

    zustand.spawn_ticks[1] = zustand.tick
    if candidates_gem_a is None:
        zustand.possible_pairs = possible_pairs
        return
    all_pos_signal = zustand.antennas.copy()

    all_pos_signal.append(Antenna(zustand.bot, zustand.signal_level))
    fade_multiplier = get_fade_by_tick(zustand, zustand.spawn_ticks[1])
    i = 0
    for pos_A in list(candidates_gem_a):
        if i > 200:
            break
        circles = []
        for antenna in all_pos_signal:
            known_signal = get_signal_from_known_gems(zustand, antenna.position)
            dist_to_gem = math.hypot(
                antenna.position[0] - pos_A[0], antenna.position[1] - pos_A[1]
            )
            gem_signal = calculate_signal(dist_to_gem, zustand)

            real_signal_min = max(
                0,
                (
                    (
                        (antenna.signal - known_signal - gem_signal)
                        - zustand.error_margin
                    )
                    / fade_multiplier
                ),
            )
            real_signal_max = min(
                1,
                (
                    (
                        (antenna.signal - known_signal - gem_signal)
                        + zustand.error_margin
                    )
                    / fade_multiplier
                ),
            )

            dist_max_sq = calculate_dist_squared_by_strength(real_signal_min, zustand)
            dist_min_sq = calculate_dist_squared_by_strength(real_signal_max, zustand)
            circles.append(
                (antenna.position[0], antenna.position[1], dist_min_sq, dist_max_sq)
            )

        valid_points = get_valid_fields_in_circles(zustand, circles)
        y_coords, x_coords = np.where(valid_points)
        candidates_B = set(zip(x_coords.tolist(), y_coords.tolist()))

        if len(candidates_B) > 0:
            # Wir haben eine gültige Kombination gefunden!
            # Wenn Gem A auf pos_A ist, muss Gem B auf einem der Felder in candidates_B sein.
            possible_pairs.append([pos_A, candidates_B])
        i += 1

    if len(possible_pairs) == 0:
        for pos_A in list(candidates_gem_a):
            if i > 200:
                break
            circles = []
            for antenna in all_pos_signal:
                known_signal = get_signal_from_known_gems(zustand, antenna.position)
                dist_to_gem = math.hypot(
                    antenna.position[0] - pos_A[0], antenna.position[1] - pos_A[1]
                )
                gem_signal = calculate_signal(dist_to_gem, zustand)

                real_signal_min = max(
                    0,
                    (
                        (
                            (antenna.signal - known_signal - gem_signal)
                            - zustand.error_margin
                        )
                        / 1
                    ),
                )
                real_signal_max = min(
                    1,
                    (
                        (
                            (antenna.signal - known_signal - gem_signal)
                            + zustand.error_margin
                        )
                        / 1
                    ),
                )

                dist_max_sq = calculate_dist_squared_by_strength(
                    real_signal_min, zustand
                )
                dist_min_sq = calculate_dist_squared_by_strength(
                    real_signal_max, zustand
                )
                circles.append(
                    (antenna.position[0], antenna.position[1], dist_min_sq, dist_max_sq)
                )

            valid_points = get_valid_fields_in_circles(zustand, circles)
            y_coords, x_coords = np.where(valid_points)
            candidates_B = set(zip(x_coords.tolist(), y_coords.tolist()))

            if len(candidates_B) > 0:
                # Wir haben eine gültige Kombination gefunden!
                # Wenn Gem A auf pos_A ist, muss Gem B auf einem der Felder in candidates_B sein.
                possible_pairs.append([pos_A, candidates_B])
            i += 1
        if len(possible_pairs) > 0:
            debug_print(f"Got Pairs Second try {len(possible_pairs)}", zustand)
            zustand.spawn_ticks[1] = zustand.tick - 15
        zustand.possible_pairs = possible_pairs
        return

    # debug_print(
    #    f"Possible pairs found: {len(possible_pairs)}, With {len(zustand.candidates[0])} candidates",
    #    zustand,
    # )
    debug_print(f"Spawn ticks: {zustand.spawn_ticks}", zustand)
    debug_print(f"Got Pairs first try {len(possible_pairs)}", zustand)
    zustand.possible_pairs = possible_pairs

    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )


def check_possible_pairs(zustand: Zustand):
    valid_pairs = []
    pos_As = set()
    pos_Bs = set()

    all_pos_signal = zustand.antennas.copy()

    all_pos_signal.append(Antenna(zustand.bot, zustand.signal_level))

    fade_multiplier = get_fade_by_tick(zustand, zustand.spawn_ticks[1])

    for pair in zustand.possible_pairs:
        pos_A = pair[0]

        if pos_A in zustand.floors:
            continue

        if zustand.saved_matrix[pos_A[1]][pos_A[0]] == "X":
            continue

        circles = []
        for antenna in all_pos_signal:
            known_signal = get_signal_from_known_gems(zustand, antenna.position)
            dist_to_gem = math.hypot(
                antenna.position[0] - pos_A[0], antenna.position[1] - pos_A[1]
            )
            gem_signal = calculate_signal(dist_to_gem, zustand)

            real_signal_min = max(
                0,
                (
                    (
                        (antenna.signal - known_signal - gem_signal)
                        - zustand.error_margin
                    )
                    / fade_multiplier
                ),
            )
            real_signal_max = min(
                1,
                (
                    (
                        (antenna.signal - known_signal - gem_signal)
                        + zustand.error_margin
                    )
                    / fade_multiplier
                ),
            )

            dist_max_sq = calculate_dist_squared_by_strength(real_signal_min, zustand)
            dist_min_sq = calculate_dist_squared_by_strength(real_signal_max, zustand)
            circles.append(
                (antenna.position[0], antenna.position[1], dist_min_sq, dist_max_sq)
            )

        valid_points = get_valid_fields_in_circles(zustand, circles)
        y_coords, x_coords = np.where(valid_points)
        candidates_B = set(zip(x_coords.tolist(), y_coords.tolist()))
        intersection_B = pair[1].intersection(candidates_B)

        if len(intersection_B) > 0:
            # Diese Hypothese lebt noch!
            pair[1] = intersection_B
            pos_As.add(pos_A)
            pos_Bs |= intersection_B
            valid_pairs.append(pair)

    zustand.possible_pairs = valid_pairs
    zustand.candidates[0] = pos_As
    zustand.candidates[1] = pos_Bs

    if len(pos_As) == 1:
        final_A = list(pos_As)[0]
        dist_A = zustand.distances_to_bot.get(final_A, None)
        if dist_A is not None:
            ttl = zustand.config.gem_ttl - (zustand.tick - zustand.spawn_ticks[0])
            zustand.remembered_gems.append(Gem(list(final_A), 280))
            to_candidates = set()
            for pair in zustand.possible_pairs:
                to_candidates |= pair[1]
            zustand.candidates[0] = to_candidates
            zustand.possible_pairs = []
            zustand.spawn_ticks[0] = zustand.spawn_ticks[1]
            zustand.spawn_ticks[1] = -1

    if len(pos_Bs) == 1:
        final_B = list(pos_Bs)[0]
        ttl = zustand.config.gem_ttl - (zustand.tick - zustand.spawn_ticks[1])
        zustand.remembered_gems.append(Gem(list(final_B), 280))
        to_candidates = set()
        for pair in zustand.possible_pairs:
            to_candidates |= {pair[0]}
        zustand.candidates[0] = to_candidates
        zustand.possible_pairs = []
        zustand.spawn_ticks[1] = -1


def check_gems(zustand: Zustand):
    valid_gems = []
    for gem in zustand.remembered_gems:
        # 1. Sofort-Check: Ist es gerade sichtbar?
        is_visible = any(
            gem.position == v_gem.position for v_gem in zustand.visible_gems
        )

        if is_visible:
            valid_gems.append(gem)
            continue  # Nächstes Gem in der Hauptschleife

        # 2. Signal-Check für nicht sichtbare Gems
        all_pos_signal = zustand.antennas.copy()
        all_pos_signal.append(Antenna(zustand.bot, zustand.signal_level))

        # Wir gehen davon aus, dass das Gem da ist, bis das Gegenteil bewiesen wird
        gem_still_there = True

        for antenna in all_pos_signal:
            dist = math.hypot(
                antenna.position[0] - gem.position[0],
                antenna.position[1] - gem.position[1],
            )
            signal_gem = calculate_signal(dist, zustand)

            # Schwellenwert: Wenn wir ein starkes Signal erwarten,
            # aber das gemessene Signal viel zu schwach ist.
            if signal_gem - (zustand.config.signal_noise * 2) > antenna.signal + 0.1:
                gem_still_there = False
                break  # Beweis gefunden, dass es weg ist -> Antennen-Loop abbrechen

        if gem_still_there:
            valid_gems.append(gem)

    zustand.remembered_gems = valid_gems


def get_valid_fields_in_circles(zustand: Zustand, circles, valid_points=None):
    # 1. Gittergröße definieren
    WIDTH = zustand.config.width  # x-Achse
    HEIGHT = zustand.config.height  # y-Achse

    # 3. 2D-Koordinatengitter erstellen
    # X ist eine 40x30 Matrix mit den x-Koordinaten, Y eine 40x30 Matrix mit den y-Koordinaten
    x_vals = np.arange(WIDTH)
    y_vals = np.arange(HEIGHT)
    X, Y = np.meshgrid(x_vals, y_vals)

    # 4. Lösungsmatrix initialisieren (Alle Punkte sind anfangs True)
    # Dies ist unser 2D-Array.
    if valid_points is None:
        valid_points = np.ones((HEIGHT, WIDTH), dtype=bool)

    matrix_np = np.array(zustand.saved_matrix)
    valid_points &= matrix_np != "X"

    # 5. Schnittmenge aller Kreisringe berechnen
    for cx, cy, r_min, r_max in circles:
        # Quadrierte Distanz jedes Gitterpunktes zum aktuellen Kreismittelpunkt
        dist_sq = (X - cx) ** 2 + (Y - cy) ** 2

        in_annulus = (dist_sq >= r_min) & (dist_sq <= r_max)

        # Logisches UND: Der Punkt muss in den bisherigen UND im aktuellen Ring liegen
        valid_points &= in_annulus

    for x, y in zustand.floors:
        valid_points[y, x] = False

    # 6. Ergebnisse extrahieren
    # valid_points ist jetzt ein 2D-Boolean-Array.
    # np.where gibt uns die exakten ganzzahligen Koordinaten der gültigen Punkte.
    # y_coords, x_coords = np.where(valid_points)
    # solution_points = list(zip(x_coords, y_coords))
    return valid_points


def precalculate_signal_offsets(zustand: Zustand):
    width = zustand.config.width
    height = zustand.config.height
    zustand.signal_offsets = dict()
    for offset_x in range(0, width):
        for offset_y in range(0, height):
            dist = math.hypot(offset_x, offset_y)
            signal = round(calculate_signal(dist, zustand), 10)
            if signal in zustand.signal_offsets:
                zustand.signal_offsets[signal].append([offset_x, offset_y])
            else:
                zustand.signal_offsets.update({signal: [[offset_x, offset_y]]})
    zustand.signal_offsets = dict(sorted(zustand.signal_offsets.items()))


def get_possible_antennas(zustand: Zustand):
    width = zustand.config.width
    height = zustand.config.height

    bot_x, bot_y = zustand.bot
    possible_antennas = []

    possible_antenna_pos = [
        (bot_x + 1, bot_y),
        (bot_x - 1, bot_y),
        (bot_x, bot_y + 1),
        (bot_x, bot_y - 1),
    ]
    random.shuffle(possible_antenna_pos)

    for antenna_x, antenna_y in possible_antenna_pos:
        if (
            zustand.saved_matrix[antenna_y][antenna_x] == "X"
            and (antenna_x, antenna_y) not in zustand.visible_antennas
        ):
            possible_antennas.append((antenna_x, antenna_y))

    if not possible_antennas:
        return None

    real_antennas = []

    for antenna in possible_antennas:
        curr_x, curr_y = antenna
        dist_mid = abs(curr_x - width // 2) + abs(curr_y - height // 2)
        if not zustand.antennas:
            real_antennas.append(antenna)
        elif zustand.antennas:
            min_dist = min(
                [
                    abs(curr_x - antenna.position[0])
                    + abs(curr_y - antenna.position[1])
                    for antenna in zustand.antennas
                ]
            )
            # Schneller placen
            if min_dist >= 8 and dist_mid <= 13:
                real_antennas.append(antenna)

    if not real_antennas:
        return None
    else:
        return real_antennas[0]


def place_antenna(antenna, zustand: Zustand):
    a_x, a_y = antenna
    b_x, b_y = zustand.bot
    if a_x > b_x:
        return "PAE"
    elif a_x < b_x:
        return "PAW"
    elif a_y > b_y:
        return "PAS"
    else:
        return "PAN"


def get_possible_fields(zustand: Zustand):
    # Feld mit [valid, tick, signal] wenn nicht besucht dann ist tick und signal = None
    possible_fields = [
        [[False, None, None] for _ in range(zustand.config.width)]
        for _ in range(zustand.config.height)
    ]

    all_pos_signal = zustand.antennas.copy()
    all_pos_signal.append(Antenna(zustand.bot, zustand.signal_level))

    circles = []
    for antenna in all_pos_signal:

        real_signal_min = 0
        real_signal_max = min(
            1,
            (((antenna.signal) + zustand.error_margin)),
        )
        dist_max_sq = calculate_dist_squared_by_strength(real_signal_min, zustand)
        dist_min_sq = calculate_dist_squared_by_strength(real_signal_max, zustand)
        circles.append(
            (antenna.position[0], antenna.position[1], dist_min_sq, dist_max_sq)
        )

    valid_points = get_valid_fields_in_circles(zustand, circles)
    y_coords, x_coords = np.where(valid_points)
    valid_fields = set(zip(x_coords.tolist(), y_coords.tolist()))
    for x in range(zustand.config.width):
        for y in range(zustand.config.height):
            if (x, y) in valid_fields:
                possible_fields[y][x][0] = True

    possible_fields[zustand.bot[1]][zustand.bot[0]][1] = zustand.tick
    possible_fields[zustand.bot[1]][zustand.bot[0]][2] = zustand.signal_level
    zustand.possible_fields = possible_fields
    zustand.highest_field = zustand.bot
    zustand.highest_signal = zustand.signal_level
    zustand.highest_fields = [zustand.bot]


def search_over_possible_fields(zustand: Zustand):
    # Feld mit [valid, tick, signal] wenn nicht besucht dann ist tick und signal = None
    zustand.possible_fields[zustand.bot[1]][zustand.bot[0]][1] = zustand.tick
    zustand.possible_fields[zustand.bot[1]][zustand.bot[0]][2] = zustand.signal_level

    if zustand.signal_level > zustand.highest_signal:
        zustand.highest_field = zustand.bot
        zustand.highest_signal = zustand.signal_level
        zustand.highest_fields.append(zustand.bot)

    # Bfs der in Ringen vom highest_field ausgeht und stoppt,
    # wenn ein Ring Felder enthält, die noch nicht besucht sind.
    # Dann werden alle noch nicht besuchten Felder angeguckt und das aus-
    # gewählt mit der niedrigsten Distanz zum Bot.

    highest_x, highest_y = zustand.highest_field
    vx, vy = 0, 0
    if len(zustand.highest_fields) > 1:
        for old_x, old_y in zustand.highest_fields[:-1]:
            vx += highest_x - old_x
            vy += highest_y - old_y

        # Normalisierung des Vektors ist für den reinen Vergleich nicht zwingend,
        # aber sauberer für die Distanzberechnung.
        mag = math.sqrt(vx**2 + vy**2)
        if mag != 0:
            vx /= mag
            vy /= mag

    queue = deque([(highest_x, highest_y)])
    visited = {(highest_x, highest_y)}

    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]

    best_field = None

    while queue:
        level_size = len(queue)
        unvisited_in_ring = []

        # Wir arbeiten exakt einen "Ring" (ein Level der Breitensuche) ab
        for _ in range(level_size):
            cx, cy = queue.popleft()

            # Wenn 'tick' None ist, wurde das Feld noch nicht besucht
            if (
                zustand.possible_fields[cy][cx][1] is None
                and zustand.saved_matrix[cy][cx] != "X"
            ):
                unvisited_in_ring.append((cx, cy))

            # Nachbarn für den nächsten Ring ermitteln
            for dx, dy in directions:
                nx, ny = cx + dx, cy + dy

                # Liegt das Feld innerhalb des Rasters?
                if 0 < ny < zustand.config.height and 0 < nx < zustand.config.width:
                    if (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append((nx, ny))

        if unvisited_in_ring:
            # ---- Scoring mit Linien-Distanz ----
            def evaluate_field(f):
                fx, fy = f
                # 1. Distanz zum Bot (Primärziel: Erreichbarkeit)
                dist_to_bot = zustand.distances_to_bot[f]

                # 2. Distanz zur Trend-Linie
                # Die Linie geht durch (hx, hy) mit Richtung (vx, vy)
                # Formel für Abstand Punkt zu Linie: |(P - H) x V|
                if vx == 0 and vy == 0:
                    line_dist = 0
                else:
                    # Kreuzprodukt im 2D (Punkt-Vektor zu Linien-Vektor)
                    line_dist = abs((fx - highest_x) * vy - (fy - highest_y) * vx)

                # Wir gewichten: Nähe zum Bot ist wichtig, aber die Linie gibt die Richtung vor.
                # Ein Feld auf der Linie hat line_dist = 0.
                return (
                    line_dist * 2.0 + dist_to_bot * 0.2
                )  # Gewichtung der Linie (anpassbar)

            best_field = min(unvisited_in_ring, key=evaluate_field)
            break
    if best_field is not None:
        return best_field
    return zustand.bot


def try_abort_search_over_possible_fields(zustand: Zustand):
    was_zero = False
    for i in range(1, 3):
        if zustand.dictionary_of_signals_and_stuff.get(zustand.tick - i) is not None:

            if (
                len(
                    zustand.dictionary_of_signals_and_stuff[zustand.tick - i][
                        "candidates"
                    ][0]
                )
                == 0
            ):
                was_zero = True
    if (
        was_zero == False
        or len(zustand.remembered_gems) > 0
        or zustand.signal_level == 0
    ):
        # Abbrechen
        zustand.possible_fields = None
        zustand.highest_field = None
        zustand.highest_signal = None
