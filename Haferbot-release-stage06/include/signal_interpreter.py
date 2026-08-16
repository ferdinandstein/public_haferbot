from bisect import bisect_left, bisect_right
from collections import deque
import random
from include.buffer import write_new_gem_msg
from include.zustand import Zustand, Gem
import math

from include.highlighting import debug_print


def calculate_signal(dist, zustand: Zustand):
    """Berechnet die Signalstärke für eine gegebene Distanz."""
    return 1 / (1 + (dist / zustand.config.signal_radius) ** 2)


def get_signal_from_gem(zustand: Zustand, gem):
    """
    Gibt das Signal für einen Gem mit Noise = 0
    """

    dist = math.hypot(
        zustand.bot[0] - gem.position[0], zustand.bot[1] - gem.position[1]
    )
    if gem.type_ == "regular":
        age = zustand.config.gem_ttl - gem.ttl
    else:
        age = zustand.config.swarm_gem_ttl - gem.ttl
    fade_multiplier = get_fade_by_tick(zustand, zustand.tick - age, gem.type_)

    new_gems = []

    for gem in zustand.gems_in_buffer:
        if zustand.distances_to_bot.get(gem.position) is not None:
            new_gems.append(gem)

    zustand.gems_in_buffer = new_gems

    signal = calculate_signal(dist, zustand) * fade_multiplier
    return signal


def get_candidates_for_signal(zustand: Zustand, signal, channel):
    """
    Berechnet mögliche Positionen basierend auf dem Restsignal.
    """
    candidates_tuples = set()
    width = zustand.config.width
    height = zustand.config.height
    # tuple set damit es schneller ist
    floors = zustand.floors

    keys = list(zustand.signal_offsets.keys())
    idx_start = bisect_left(keys, signal - 0.0009)
    idx_end = bisect_right(keys, signal + 0.0009)
    bx = zustand.bot[0]
    by = zustand.bot[1]

    for i in range(idx_start, idx_end):
        current_signal = keys[i]
        offsets = zustand.signal_offsets[current_signal]
        # 4 Quadranten berücksichtigen
        for dx, dy in offsets:
            # Symmetrie-Punkte generieren
            for nx, ny in (
                (bx + dx, by + dy),
                (bx + dx, by - dy),
                (bx - dx, by + dy),
                (bx - dx, by - dy),
            ):

                # Bounds Check
                if 0 < nx < width and 0 < ny < height:
                    if zustand.saved_matrix[ny][nx] == "X":
                        continue

                    if (nx, ny) in floors:
                        continue
                    dist = math.hypot(
                        zustand.last_bot[0] - nx, zustand.last_bot[1] - ny
                    )

                    if (
                        zustand.last_signal_channels[channel] == 0
                        and dist >= zustand.cutoff_dist
                    ):
                        candidates_tuples.add((nx, ny))
                    elif zustand.last_signal_channels[channel] > 0:
                        candidates_tuples.add((nx, ny))
    candidates = candidates_tuples
    return candidates


def get_fade_by_tick(zustand: Zustand, tick, type_):
    """Berechnet den Fade-Multiplikator basierend auf dem Spawntick des Gems."""
    age = zustand.tick - tick
    signal_fade = zustand.config.signal_fade

    if type_ == "swarm":
        config_ttl = zustand.config.swarm_gem_ttl
    else:
        config_ttl = zustand.config.gem_ttl

    if age == 0 or age >= config_ttl:
        return signal_fade

    if age < signal_fade:
        fade_multiplier = signal_fade / (age)
    elif age >= config_ttl - signal_fade:
        fade_multiplier = signal_fade / (config_ttl - age)
    else:
        fade_multiplier = 1

    return fade_multiplier


def sort_gems_by_distance(gem: Gem, zustand: Zustand):
    """Funktion, um Gems nach ihrer Entfernung zum Bot zu sortieren."""
    dist = zustand.distances_to_bot[gem.position]
    if dist > 0:
        res = 1 / dist
    else:
        res = 10000

    return res


def calc_candidates_for_channels(zustand: Zustand):
    """Berechnet die Kandidatenpositionen für alle Kanäle basierend auf den aktuellen Signalen und bekannten Informationen."""
    import time

    start_time = time.perf_counter_ns()

    channels = zustand.signal_channels
    blocked_channels = set()
    for gem in zustand.remembered_gems:
        blocked_channels.add(gem.channel)
    for gem in zustand.gems_in_buffer:
        blocked_channels.add(gem.channel)
        zustand.candidates[gem.channel] = set()
    for channel in range(zustand.config.max_gems):

        if channels[channel] == 0:
            zustand.no_signal_streak[channel] += 1
            if zustand.no_signal_streak[channel] > 3:
                zustand.candidates[channel] = set()
        elif channel in blocked_channels:
            zustand.no_signal_streak[channel] = 0
            continue
        else:
            zustand.no_signal_streak[channel] = 0
            if zustand.discovered_in_tick[channel] == -1:
                if abs(channels[channel] - zustand.config.signal_cutoff) < 0.01:
                    debug_print(
                        f"Channel {channel} is likely walked in. Signal: {channels[channel]}",
                        zustand,
                    )
                    zustand.discovered_in_tick[channel] = (
                        zustand.tick - zustand.config.signal_fade - 1
                    )
                else:
                    debug_print(
                        f"Channel {channel} is likely spawned. Signal: {channels[channel]} Tick: {zustand.tick -1}",
                        zustand,
                    )
                    zustand.discovered_in_tick[channel] = zustand.tick - 1

            fade_multiplier = get_fade_by_tick(
                zustand, zustand.discovered_in_tick[channel], "regular"
            )

            real_signal = channels[channel] * fade_multiplier

            step_candidates = get_candidates_for_signal(zustand, real_signal, channel)
            if len(zustand.candidates[channel]) > 0:
                intersection = zustand.candidates[channel].intersection(step_candidates)
                zustand.candidates[channel] = intersection
            else:
                zustand.candidates[channel] = step_candidates
                intersection = step_candidates
            if len(intersection) == 1:
                found_pos = list(intersection)[0]
                # Prüfen, ob wir den versehentlich schon kennen (sollte durch residual logic nicht passieren, aber sicher ist sicher)
                already_known = False
                for gem in zustand.remembered_gems:
                    if gem.position == found_pos:
                        already_known = True

                if not already_known:

                    # Gem erstellen und speichern
                    dist = zustand.distances_to_bot.get(found_pos, None)
                    if dist is not None:
                        type_ = "regular"
                        new_gem_data = {
                            "position": found_pos,
                            "ttl": zustand.config.gem_ttl
                            - (zustand.tick - zustand.discovered_in_tick[channel]),
                            "type": type_,
                            "channel": channel,
                        }
                        new_gem_obj = Gem(**new_gem_data)
                        zustand.remembered_gems.append(new_gem_obj)
                        debug_print(
                            f"Found new gem at {found_pos} on channel {channel} writing it in buffer.",
                            zustand,
                        )
                        write_new_gem_msg(new_gem_obj, zustand)
                        zustand.remembered_gems.sort(
                            key=lambda gem: sort_gems_by_distance(gem, zustand),
                            reverse=True,
                        )

                        zustand.candidates[channel] = set()
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )


def precalculate_signal_offsets(zustand: Zustand):
    """Berechnet im Vorfeld die möglichen Signalstärken für alle Offset-Kombinationen und speichert sie in einem Dictionary, um die spätere Suche zu beschleunigen."""
    width = zustand.config.width
    height = zustand.config.height
    zustand.signal_offsets = {}
    for offset_x in range(0, width):
        for offset_y in range(0, height):
            dist = math.hypot(offset_x, offset_y)
            signal = round(calculate_signal(dist, zustand), 10)
            if signal in zustand.signal_offsets:
                zustand.signal_offsets[signal].append([offset_x, offset_y])
            else:
                zustand.signal_offsets.update({signal: [[offset_x, offset_y]]})
    zustand.signal_offsets = dict(sorted(zustand.signal_offsets.items()))


def get_hypothetical_gems_from_candidates(zustand: Zustand):
    """Basierend auf den aktuellen Kandidatenpositionen und Signalen, berechnet diese Funktion die hypothetischen Gems, die wahrscheinlich existieren, und aktualisiert den Zustand entsprechend."""
    import time

    start_time = time.perf_counter_ns()
    last_gems = zustand.hypothetical_gems
    last_gems_map = {g.channel: g for g in last_gems}

    current_tick = zustand.tick
    max_ttl = zustand.config.gem_ttl

    zustand.hypothetical_gems = []
    blocked_channels = {gem.channel for gem in zustand.remembered_gems}
    for gem in zustand.gems_in_buffer:
        blocked_channels.add(gem.channel)
    reseted_channels = {
        channel: pos[0] for channel, pos in enumerate(zustand.reseted_channels) if pos
    }

    # 2. Kanäle durchgehen
    for channel in range(zustand.config.max_gems):
        if channel in blocked_channels or len(zustand.candidates[channel]) == 0:
            continue

        candidates = zustand.candidates[channel]

        if channel in reseted_channels:
            x, y = reseted_channels[channel]
            if reseted_channels[channel] in candidates:
                best_pos = reseted_channels[channel]
            else:
                best_pos = min(
                    candidates,
                    key=lambda p, x=x, y=y: (p[0] - x) ** 2 + (p[1] - y) ** 2,
                )
            age = current_tick - zustand.discovered_in_tick[channel]
            ttl = max_ttl - age
            zustand.hypothetical_gems.append(
                Gem(list(best_pos), ttl, "regular", channel)
            )
            continue

        # Cluster-Funktion gibt (Punkte-Set, Score) zurück
        clusters = cluster_candidates(candidates, zustand)

        if not clusters:
            continue

        main_cluster, _ = clusters[0]
        c_len = len(main_cluster)

        if c_len <= 1000:
            sum_x = sum_y = 0
            for px, py in main_cluster:
                sum_x += px
                sum_y += py

            avg_x, avg_y = sum_x / c_len, sum_y / c_len

            best_pos = min(
                main_cluster,
                key=lambda p, x=avg_x, y=avg_y: (p[0] - x) ** 2 + (p[1] - y) ** 2,
            )

            age = current_tick - zustand.discovered_in_tick[channel]
            ttl = max_ttl - age
            if ttl > 0:
                zustand.hypothetical_gems.append(
                    Gem(list(best_pos), ttl, "regular", channel)
                )

        elif channel in last_gems_map:
            last_gem = last_gems_map[channel]
            if tuple(last_gem.position) in main_cluster:
                last_gem.ttl -= 1
                zustand.hypothetical_gems.append(last_gem)

    # 3. Effizienter Vergleich am Ende (O(N) statt O(N*M))
    if last_gems and len(last_gems) == len(zustand.hypothetical_gems):
        curr_positions = {tuple(g.position) for g in zustand.hypothetical_gems}
        last_positions = {tuple(g.position) for g in last_gems}

        if curr_positions == last_positions:
            for g in last_gems:
                g.ttl -= 1
            zustand.hypothetical_gems = last_gems

    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )


def cluster_candidates(candidates: list, zustand: Zustand):
    """Clustert die KAndidaten basierend auf ihrer räumlichen Nähe und berechnet einen Score für jedes Cluster, um die wahrscheinlichsten Positionen zu identifizieren."""
    if not candidates:
        return []

    matrix = zustand.saved_matrix
    candidates_set = set(candidates)  # candidates sind oft schon tuples
    visited = set()
    clusters_with_scores = []

    # Offsets als Konstante (lokal)
    offsets = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    diagonals = [(1, 1), (-1, 1), (-1, -1), (1, -1)]

    for start_node in candidates:
        if start_node in visited:
            continue

        queue = deque([start_node])
        visited.add(start_node)

        current_cluster = set()
        distances = []
        unknowns = 0

        while queue:
            cx, cy = queue.popleft()
            current_cluster.add((cx, cy))
            distances.append(zustand.distances_to_bot[(cx, cy)])

            if matrix[cy][cx] == "/":
                unknowns += 1

            # 1. Gerade Nachbarn
            for dx, dy in offsets:
                neighbor = (cx + dx, cy + dy)
                if neighbor in candidates_set and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

            # 2. Diagonale Nachbarn mit Wall-Check
            for dx, dy in diagonals:
                neighbor = (cx + dx, cy + dy)
                if neighbor in candidates_set and neighbor not in visited:
                    # Wall-Check: Nur wenn der Durchgang nicht blockiert ist
                    if not (matrix[cy][cx + dx] == "X" and matrix[cy + dy][cx] == "X"):
                        visited.add(neighbor)
                        queue.append(neighbor)

        if current_cluster:
            # Score direkt berechnen
            score = len(current_cluster) - (
                unknowns * zustand.weights.s_field_unknown_weight
            )
            clusters_with_scores.append((current_cluster, score))

    # Sortierung nutzt jetzt den bereits berechneten Score
    clusters_with_scores.sort(key=lambda x: x[1], reverse=True)
    return clusters_with_scores
