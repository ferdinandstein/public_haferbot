from include.zustand import Position, Zustand, Gem
import math
from collections import defaultdict
from include.pfad_und_routen import check_for_new_path

from include.pathfinding_logics import (
    generate_a_star_path,
    follow_a_star_path,
)
from include.checks import check_if_destination_in_gems

from include.highlighting import debug_print


def calculate_signal(dist, zustand: Zustand):
    """Berechnet die Signalstärke für eine gegebene Distanz."""
    return 1 / (1 + (dist / zustand.config.signal_radius) ** 2)


def get_signal_from_known_gems(zustand: Zustand):
    """
    Summiert die Signale aller Gems, die wir bereits kennen (in remembered_gems sind).
    Damit können wir diese vom Gesamtsignal abziehen (Subtraktion).
    """
    total_known_signal = 0
    for gem in zustand.remembered_gems:
        dist = math.hypot(
            zustand.bot.x - gem.position.x, zustand.bot.y - gem.position.y
        )
        total_known_signal += calculate_signal(dist, zustand)
    return total_known_signal


def get_candidates_for_residual(zustand: Zustand, residual_signal):
    """
    Berechnet mögliche Positionen basierend auf dem Restsignal.
    """
    candidates = set()
    width = zustand.config.width
    height = zustand.config.height
    first_valid = 0

    for item in zustand.signal_offsets.keys():
        if abs(item - residual_signal) < 0.000005:
            if first_valid == 0:
                first_valid = 1
            possible_positions = set()
            offsets = zustand.signal_offsets[item]
            # 4 Quadranten berücksichtigen
            for offset in offsets:
                possible_positions.add(
                    Position([zustand.bot.x + offset[0], zustand.bot.y + offset[1]])
                )
                possible_positions.add(
                    Position([zustand.bot.x + offset[0], zustand.bot.y - offset[1]])
                )
                possible_positions.add(
                    Position([zustand.bot.x - offset[0], zustand.bot.y + offset[1]])
                )
                possible_positions.add(
                    Position([zustand.bot.x - offset[0], zustand.bot.y - offset[1]])
                )

            for pos in possible_positions:
                if 0 < pos.x < width and 0 < pos.y < height:
                    # Wände ignorieren
                    if zustand.saved_matrix[pos.y][pos.x] == "X":
                        continue

                    if pos in zustand.floors:
                        continue

                    candidates.add(pos)
        elif first_valid == 1:
            break
    return candidates


def calc_candidates(zustand: Zustand):
    known_signal = get_signal_from_known_gems(zustand)

    residual_signal = zustand.signal_level - known_signal
    residual_signal = round(residual_signal, 6)  # Float-Fehler vermeiden
    if residual_signal > 0.0001:  # Kleiner Threshold gegen Rauschen

        # A. Kandidaten für DIESEN Tick berechnen
        step_candidates = get_candidates_for_residual(zustand, residual_signal)

        # B. Schnittmenge bilden (Intersection)
        if (
            (zustand.current_candidates is None or len(zustand.current_candidates) == 0)
            and len(step_candidates) > 0
        ):
            # Start einer neuen Suche
            zustand.discovered_in_tick_A = zustand.tick
            zustand.current_candidates = step_candidates
            # debug_print("Starting new search", zustand)
        else:
            # Suche läuft schon: Wir behalten nur Kandidaten, die in BEIDEN Sets sind
            intersection = zustand.current_candidates.intersection(step_candidates)
            # debug_print(f"Intersection {len(intersection)}", zustand)

            if len(intersection) == 0:
                # KONFLIKT: Die alten Kandidaten passen nicht zu den neuen.
                # Gründe:
                # 1. der Bot hat einen falschen Gem eingetragen
                # 2. Ein neuer ist aufgetaucht
                identified_gem = identify_phantom_gem(zustand)
                if identified_gem is not None:
                    zustand.remembered_gems.remove(identified_gem)
                    debug_print("remove by phantom", zustand)
                    residual_signal = zustand.signal_level - get_signal_from_known_gems(
                        zustand
                    )
                    candidates = get_candidates_for_residual(zustand, residual_signal)
                    intersection = zustand.current_candidates.intersection(candidates)
                    if len(intersection) > 1:
                        zustand.current_candidates = intersection
                    elif len(intersection) == 1:
                        zustand.current_candidates = intersection
                        found_pos = list(zustand.current_candidates)[0]
                        # Prüfen, ob wir den versehentlich schon kennen (sollte durch residual logic nicht passieren, aber sicher ist sicher)
                        already_known = False
                        for gem in zustand.remembered_gems:
                            # Zugriff anpassen, falls g.position anders strukturiert ist
                            if gem.position == found_pos:
                                already_known = True

                        if not already_known:

                            # Gem erstellen und speichern
                            dist = zustand.distances_to_bot.get(found_pos, None)
                            if dist is not None:
                                new_gem_data = {
                                    "position": [found_pos.x, found_pos.y],
                                    "ttl": zustand.config.gem_ttl
                                    - (zustand.tick - zustand.discovered_in_tick_A),
                                }
                                new_gem_obj = Gem(**new_gem_data)
                                zustand.remembered_gems.append(new_gem_obj)

                                # Suche zurücksetzen, damit wir bereit für den nächsten (dritten) Gem sind
                                zustand.current_candidates = set()
                                zustand.last_candidates = set()
                    return
                else:
                    possible_swaps = solve_swap_situation(zustand, residual_signal)

                    if len(possible_swaps) == 0:
                        # debug_print(
                        #    "Kein Gem zum Entfernen gefunden! Irgendwas ist faul!!", zustand
                        # )
                        zustand.possible_points = zustand.current_candidates
                        zustand.current_candidates = set()
                        return
                    elif len(zustand.possible_swaps) == 0:
                        # debug_print(f"Taking valid swaps {len(possible_swaps)}", zustand)
                        zustand.possible_swaps = possible_swaps
                        zustand.possible_points = zustand.current_candidates
                        zustand.current_candidates = set()
                        return
            else:
                zustand.current_candidates = intersection

        # C. Haben wir ihn gefunden?
        if len(zustand.current_candidates) == 1:
            # Treffer! Position extrahieren
            found_pos = list(zustand.current_candidates)[0]

            # Prüfen, ob wir den versehentlich schon kennen (sollte durch residual logic nicht passieren, aber sicher ist sicher)
            already_known = False
            for gem in zustand.remembered_gems:
                # Zugriff anpassen, falls g.position anders strukturiert ist
                if gem.position == found_pos:
                    already_known = True

            if not already_known:

                # Gem erstellen und speichern
                dist = zustand.distances_to_bot.get(found_pos, None)
                if dist is not None:
                    new_gem_data = {
                        "position": [found_pos.x, found_pos.y],
                        "ttl": zustand.config.gem_ttl
                        - (zustand.tick - zustand.discovered_in_tick_A),
                    }
                    new_gem_obj = Gem(**new_gem_data)
                    zustand.remembered_gems.append(new_gem_obj)

                    # Suche zurücksetzen, damit wir bereit für den nächsten (dritten) Gem sind
                    zustand.current_candidates = set()
                    zustand.last_candidates = set()

    elif residual_signal < -0.0001:
        # Gem ist weg.
        removed = False
        for gem in zustand.remembered_gems:
            dist = math.hypot(
                gem.position.x - zustand.bot.x, gem.position.y - zustand.bot.y
            )
            gem_signal = calculate_signal(dist, zustand)
            if abs(gem_signal + residual_signal) <= 0.00001:
                removed = True
                zustand.remembered_gems.remove(gem)
                # debug_print("Das war einfach", zustand)
                break
        if removed == False:
            posibble_gone_gems = []
            for gem in zustand.remembered_gems:
                visible = False
                for visible_gem in zustand.visible_gems:
                    if gem.position == visible_gem.position:
                        visible = True
                        break
                if visible == False:
                    posibble_gone_gems.append(gem)

            if len(posibble_gone_gems) == 1:
                zustand.remembered_gems.remove(posibble_gone_gems[0])
                # debug_print("Visibility", zustand)
                removed = True
        if removed == False:
            zustand.possible_swaps = solve_swap_situation(zustand, residual_signal)
            if len(zustand.possible_swaps) == 1:
                gem_to_remove = zustand.possible_swaps[0]["gem_removed"]
                zustand.remembered_gems.remove(gem_to_remove)
                removed = True
                zustand.current_candidates = zustand.possible_swaps[0]["candidates"]
                zustand.possible_swaps = []
                zustand.discovered_in_tick_A = zustand.tick
                return
            elif len(zustand.possible_swaps) == 0:
                debug_print(
                    "Kein Gem zum Entfernen gefunden! Irgendwas ist faul!!", zustand
                )
        # if removed == False:
        #    new_duos = resolve_two_unknown_gems(zustand)
        #    if len(new_duos) > 0 and len(zustand.possible_duos) == 0:
        #        debug_print("Konflikt in Kandidaten - Starte Duosuche", zustand)
        #        zustand.possible_duos = new_duos

        if removed == True:
            residual_signal = zustand.signal_level - get_signal_from_known_gems(zustand)
            zustand.current_candidates = get_candidates_for_residual(
                zustand, residual_signal
            )
            zustand.discovered_in_tick_A = zustand.tick
        else:
            zustand.current_candidates = set()

    else:
        # Restsignal ist ~0. Wir kennen alle Gems.
        zustand.last_candidates = set()
        zustand.current_candidates = set()


def identify_phantom_gem(zustand: Zustand):
    """
    Prüft, ob das Entfernen eines bekannten Gems den Konflikt lösen würde.
    Gibt den Gem zurück, dessen Entfernung dazu führt
    """
    # Wir iterieren über alle Gems, die wir "glauben" zu haben
    for suspect_gem in zustand.remembered_gems:
        # Prüfen ob der Gem in visible_gems ist (nach Position vergleichen)
        is_visible = False
        for visible_gem in zustand.visible_gems:
            if suspect_gem.position == visible_gem.position:
                is_visible = True
                break
        if is_visible:
            continue

        # 1. Berechne das Signal OHNE diesen Verdächtigen
        # Wir ziehen das Signal des Verdächtigen vom bekannten Signal ab
        dist = math.hypot(
            suspect_gem.position.x - zustand.bot.x,
            suspect_gem.position.y - zustand.bot.y,
        )
        suspect_signal = calculate_signal(dist, zustand)

        # Das bekannte Signal reduziert um den Verdächtigen
        known_signal_without_suspect = (
            get_signal_from_known_gems(zustand) - suspect_signal
        )

        # Neues hypothetisches Residual
        hypothetical_residual = zustand.signal_level - known_signal_without_suspect

        # 2. Macht dieses Residual Sinn? (Muss > 0 sein)
        if hypothetical_residual < 0:
            continue
        if hypothetical_residual < 0.0001:
            return suspect_gem

        # 3. Berechne Kandidaten für dieses hypothetische Szenario
        # hypo_candidates = get_candidates_for_residual(zustand, hypothetical_residual)
    # if len(hypo_candidates) > 0:
    #   return suspect_gem

    return None


def solve_swap_situation(zustand: Zustand, residual_signal):
    possible_swaps = []

    for gem in zustand.remembered_gems:
        if gem in zustand.visible_gems:
            continue
        dist_old = math.hypot(
            gem.position.x - zustand.bot.x, gem.position.y - zustand.bot.y
        )
        signal_old = calculate_signal(dist_old, zustand)

        # Hypothese: Neu = Residual + Alt
        signal_new_hypothetical = residual_signal + signal_old

        if (
            0.0001 < signal_new_hypothetical < 0.9
        ):  # Toleranz nach oben etwas weiter für Rundungsfehler

            possible_swaps.append(
                {
                    "gem_removed": gem,
                    "signal_new": signal_new_hypothetical,
                    "candidates": get_candidates_for_residual(
                        zustand, signal_new_hypothetical
                    ),
                }
            )

    if not possible_swaps:
        return []
    else:
        return possible_swaps


def check_possible_swaps(zustand: Zustand):
    new_swaps = []
    for swap in zustand.possible_swaps:
        gem = swap["gem_removed"]
        residual_signal = zustand.signal_level - get_signal_from_known_gems(zustand)
        gem_dist = math.hypot(
            gem.position.x - zustand.bot.x, gem.position.y - zustand.bot.y
        )
        gem_signal = calculate_signal(gem_dist, zustand)
        residual_signal_hypothecialy = residual_signal + gem_signal
        candidates_now = get_candidates_for_residual(
            zustand, residual_signal_hypothecialy
        )
        intersection = candidates_now.intersection(swap["candidates"])
        if len(intersection) == 0:
            continue
        else:
            swap["candidates"] = intersection
            new_swaps.append(swap)

    if len(new_swaps) == 1:
        zustand.remembered_gems.remove(new_swaps[0]["gem_removed"])
        zustand.current_candidates = new_swaps[0]["candidates"]
        new_swaps = []
    zustand.possible_swaps = new_swaps


def circle_around(zustand: Zustand, destination: Position):
    # Alle 8 Felder um den Gem herum in korrekter Reihenfolge (im Uhrzeigersinn)
    # Relativ zum Gem (0,0)
    import time

    start_time = time.perf_counter_ns()
    offsets_clockwise = [
        (-1, -1),
        (0, -1),
        (1, -1),
        (1, 0),
        (1, 1),
        (0, 1),
        (-1, 1),
        (-1, 0),
    ]
    offsets_anti_clockwise = [
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, 1),
        (1, 1),
        (1, 0),
        (1, -1),
        (0, -1),
    ]

    # 1. Die absoluten Positionen des Rings berechnen
    ring_positions_clockwise = []
    for dx, dy in offsets_clockwise:
        px, py = destination.x + dx, destination.y + dy
        # Prüfen, ob im Spielfeld
        ring_positions_clockwise.append(Position([px, py]))

    ring_positions_anti_clockwise = []
    for dx, dy in offsets_anti_clockwise:
        px, py = destination.x + dx, destination.y + dy
        # Prüfen, ob im Spielfeld
        ring_positions_anti_clockwise.append(Position([px, py]))

    # 2. Den Startpunkt finden (wo steht der Bot gerade am nächsten?)
    # Wir suchen den Index im Ring, der dem Bot am nächsten ist
    start_idx_clockwise = 0
    min_dist_clockwise = float("inf")
    for i, pos in enumerate(ring_positions_clockwise):
        d = math.hypot(zustand.bot.x - pos.x, zustand.bot.y - pos.y)
        if d < min_dist_clockwise:
            min_dist_clockwise = d
            start_idx_clockwise = i

    start_idx_anti_clockwise = 0
    min_dist_anti_clockwise = float("inf")
    for i, pos in enumerate(ring_positions_anti_clockwise):
        d = math.hypot(zustand.bot.x - pos.x, zustand.bot.y - pos.y)
        if d < min_dist_anti_clockwise:
            min_dist_anti_clockwise = d
            start_idx_anti_clockwise = i

    # 3. Den Pfad zusammenbauen
    # Wir rotieren den Ring so, dass er beim start_idx beginnt
    rotated_path_clockwise = (
        ring_positions_clockwise[start_idx_clockwise:]
        + ring_positions_clockwise[:start_idx_clockwise]
    )
    rotated_path_clockwise.pop(-1)
    real_path_clockwise = []
    for point_clockwise in rotated_path_clockwise:
        if 0 <= point_clockwise.x < zustand.config.width and 0 <= point_clockwise.y < zustand.config.height:
            if zustand.saved_matrix[point_clockwise.y][point_clockwise.x] == "X":
                break
            else:
                real_path_clockwise.append(point_clockwise)

    if len(real_path_clockwise) % 2 == 0:
        real_path_clockwise.pop(-1)

    #########################################

    rotated_path_anti_clockwise = (
        ring_positions_anti_clockwise[start_idx_anti_clockwise:]
        + ring_positions_anti_clockwise[:start_idx_anti_clockwise]
    )
    rotated_path_anti_clockwise.pop(-1)
    real_path_anti_clockwise = []
    for point_anti_clockwise in rotated_path_anti_clockwise:
        if 0 <= point_anti_clockwise.x < zustand.config.width and 0 <= point_anti_clockwise.y < zustand.config.height:
            if zustand.saved_matrix[point_anti_clockwise.y][point_anti_clockwise.x] == "X":
                break
            else:
                real_path_anti_clockwise.append(point_anti_clockwise)

    if len(real_path_anti_clockwise) % 2 == 0:
        real_path_anti_clockwise.pop(-1)

    # 4. Den Zielpunkt (den Gem selbst) am Ende hinzufügen
    real_path_clockwise.append(destination)
    real_path_anti_clockwise.append(destination)

    if len(real_path_clockwise) > len(real_path_anti_clockwise):
        path = real_path_clockwise
    else:
        path = real_path_anti_clockwise

    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )

    return path


def check_for_circling(zustand: Zustand):
    if check_if_destination_in_gems(zustand) == True:
        known_signal = get_signal_from_known_gems(zustand)
        residual_signal = zustand.signal_level - known_signal

        distance = zustand.distances_to_bot.get(zustand.destination)
        near = False
        if zustand.opponent is not None:
            opponent_dist = zustand.distances_to_bot.get(zustand.opponent)
            if opponent_dist is not None and opponent_dist < 3:
                near = True

        if distance is not None and distance < 2 and zustand.with_opponent == True and near == "Falsex":

            if abs(residual_signal) > 0.001:
                if zustand.circling == False:
                    # Unidentified last_gem
                    zustand.a_star_path = circle_around(zustand, zustand.destination)

                    zustand.circling = True

            else:

                if zustand.circling == True:
                    zustand.a_star_path = generate_a_star_path(
                        zustand, zustand.destination, zustand.bot
                    )
                    zustand.circling = False

    else:
        last_destination = zustand.destination
        check_for_new_path(zustand)
        if zustand.destination != last_destination:
            zustand.a_star_path = generate_a_star_path(
                zustand, zustand.destination, zustand.bot
            )
        zustand.circling = False
    return follow_a_star_path(zustand)


def get_possible_pairs(zustand: Zustand):
    """
    Versucht, zwei Gems zu lokalisieren, indem wir annehmen, dass einer davon
    aus der Liste candidates_gem_A stammt.

    Returns: Eine Liste von Tupeln: [ (PosA1, [PosB_Candidates]), (PosA2, [PosB_Candidates]), ... ]
    """
    import time

    start_time = time.perf_counter_ns()
    candidates_gem_a = zustand.last_candidates
    possible_pairs = []
    bot_pos = zustand.bot
    known = get_signal_from_known_gems(zustand)
    current_residual = zustand.signal_level - known
    zustand.discovered_in_tick_B = zustand.tick

    # Wir iterieren durch jeden Kandidaten, den wir für den ERSTEN Gem hatten
    for pos_A in candidates_gem_a:
        # 1. Hypothese: Wie viel Signal würde Gem A an meiner jetzigen Position erzeugen?
        dist_A = math.hypot(bot_pos.x - pos_A.x, bot_pos.y - pos_A.y)
        signal_A_theoretical = calculate_signal(dist_A, zustand)

        # 2. Was bleibt für den NEUEN Gem B übrig?
        # current_residual ist das gemessene Signal minus die BEREITS BEKANNTEN (gesicherten) Gems.
        signal_B_needed = current_residual - signal_A_theoretical

        # 3. Validierung: Ist das ein realistisches Signal für einen Gem?
        # Es muss > 0 sein und darf nicht > 1 sein (außer wir stehen drauf)
        if signal_B_needed < 0.001:
            continue  # Unmöglich, Gem B hätte negatives Signal
        if signal_B_needed > 0.9:
            continue  # Unmöglich, Gem B wäre neben uns

        # 4. Wo könnte Gem B sein? (Umkehrfunktion der Signalformel)
        # Wir nutzen deine existierende Logik, aber mit dem spezifischen Rest-Signal
        candidates_B = get_candidates_for_residual(zustand, signal_B_needed)

        if len(candidates_B) > 0:
            # Wir haben eine gültige Kombination gefunden!
            # Wenn Gem A auf pos_A ist, muss Gem B auf einem der Felder in candidates_B sein.
            possible_pairs.append(
                {"gem_A_pos": pos_A, "gem_B_candidates": candidates_B}
            )
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
    known = get_signal_from_known_gems(zustand)
    current_residual = zustand.signal_level - known
    pos_As = set()
    pos_Bs = set()

    for pair in zustand.possible_pairs:
        pos_A = pair["gem_A_pos"]

        if pos_A in zustand.floors:
            continue

        if zustand.saved_matrix[pos_A.y][pos_A.x] == "X":
            continue

        # Wir berechnen wieder: Was müsste Gem B JETZT für ein Signal haben,
        # wenn A auf pos_A liegt?
        dist = math.hypot(zustand.bot.x - pos_A.x, zustand.bot.y - pos_A.y)
        signal_A = calculate_signal(dist, zustand)

        sig_B_expected = current_residual - signal_A

        # Neue Kandidaten für B berechnen
        new_candidates_B = get_candidates_for_residual(zustand, sig_B_expected)

        # Schnittmenge mit den alten B-Kandidaten dieser Hypothese bilden
        intersection_B = pair["gem_B_candidates"].intersection(new_candidates_B)

        if len(intersection_B) > 0:
            # Diese Hypothese lebt noch!
            pair["gem_B_candidates"] = intersection_B
            pos_As.add(pos_A)
            pos_Bs |= intersection_B
            valid_pairs.append(pair)
    zustand.current_candidates = pos_As

    zustand.possible_pairs = valid_pairs
    if len(pos_As) == 1:
        final_A = list(pos_As)[0]
        dist_A = zustand.distances_to_bot.get(final_A, None)
        if dist_A is not None:
            new_gem_data_A = {
                "position": [final_A.x, final_A.y],
                "ttl": zustand.config.gem_ttl
                - (zustand.tick - zustand.discovered_in_tick_A),
            }
            new_gem_obj_A = Gem(**new_gem_data_A)
            zustand.remembered_gems.append(new_gem_obj_A)
            to_candidates = set()
            for pair in zustand.possible_pairs:
                to_candidates |= pair["gem_B_candidates"]
            zustand.current_candidates = to_candidates
            zustand.possible_pairs = []

    if len(pos_Bs) == 1:
        final_B = list(pos_Bs)[0]
        new_gem_data_B = {
            "position": [final_B.x, final_B.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - zustand.discovered_in_tick_B),
        }
        new_gem_obj_B = Gem(**new_gem_data_B)
        zustand.remembered_gems.append(new_gem_obj_B)
        to_candidates = set()
        for pair in zustand.possible_pairs:
            to_candidates.add(pair["gem_A_pos"])
        zustand.current_candidates = to_candidates
        zustand.possible_pairs = []

    # Check: Haben wir es gelöst?
    if (
        len(zustand.possible_pairs) == 1
        and len(zustand.possible_pairs[0]["gem_B_candidates"]) == 1
    ):
        # BINGO! Beide gefunden.
        final_A = zustand.possible_pairs[0]["gem_A_pos"]
        final_B = list(zustand.possible_pairs[0]["gem_B_candidates"])[0]
        new_gem_data_A = {
            "position": [final_A.x, final_A.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - zustand.discovered_in_tick_A),
        }
        new_gem_obj_A = Gem(**new_gem_data_A)
        zustand.remembered_gems.append(new_gem_obj_A)

        new_gem_data_B = {
            "position": [final_B.x, final_B.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - zustand.discovered_in_tick_B),
        }
        new_gem_obj_B = Gem(**new_gem_data_B)
        zustand.remembered_gems.append(new_gem_obj_B)
        zustand.possible_pairs = []


def get_possible_triples(zustand: Zustand):
    possible_pairs = zustand.last_possible_pairs
    possible_triples = []
    bot_pos = zustand.bot
    known = get_signal_from_known_gems(zustand)
    current_residual = zustand.signal_level - known
    zustand.discovered_in_tick_C = zustand.tick

    # Wir iterieren durch jeden Kandidaten, den wir für den ERSTEN Gem hatten
    for pair in possible_pairs:
        pos_A = pair["gem_A_pos"]
        dist_A = math.hypot(bot_pos.x - pos_A.x, bot_pos.y - pos_A.y)
        signal_A_theoretical = calculate_signal(dist_A, zustand)

        for pos_B in set(pair["gem_B_candidates"]):
            dist_B = math.hypot(bot_pos.x - pos_B.x, bot_pos.y - pos_B.y)
            signal_B_theoretical = calculate_signal(dist_B, zustand)
            # current_residual ist das gemessene Signal minus die BEREITS BEKANNTEN (gesicherten) Gems.
            signal_C_needed = (
                current_residual - signal_A_theoretical - signal_B_theoretical
            )

            # 3. Validierung: Ist das ein realistisches Signal für einen Gem?
            # Es muss > 0 sein und darf nicht > 1 sein (außer wir stehen drauf)
            if signal_C_needed < 0.001:
                continue  # Unmöglich, Gem C hätte negatives Signal
            if signal_C_needed > 0.9:
                continue  # Unmöglich, Gem C wäre neben uns

            # 4. Wo könnte Gem C sein? (Umkehrfunktion der Signalformel)
            # Wir nutzen deine existierende Logik, aber mit dem spezifischen Rest-Signal
            candidates_C = get_candidates_for_residual(zustand, signal_C_needed)

            if len(candidates_C) > 0:
                # Wir haben eine gültige Kombination gefunden!
                # Wenn Gem A auf pos_A ist und Gem B auf pos_B, muss Gem C auf einem der Felder in candidates_C sein.
                possible_triples.append(
                    {
                        "gem_A_pos": pos_A,
                        "gem_B_pos": pos_B,
                        "gem_C_candidates": candidates_C,
                    }
                )
    zustand.possible_triples = possible_triples


def check_possible_triples(zustand: Zustand):
    valid_triples = []
    known = get_signal_from_known_gems(zustand)
    current_residual = zustand.signal_level - known
    pos_As = set()
    pos_Bs = set()
    pos_Cs = set()

    for triple in zustand.possible_triples:
        pos_A = triple["gem_A_pos"]

        if pos_A in zustand.floors:
            continue

        if zustand.saved_matrix[pos_A.y][pos_A.x] == "X":
            continue

        dist = math.hypot(zustand.bot.x - pos_A.x, zustand.bot.y - pos_A.y)
        signal_A = calculate_signal(dist, zustand)
        pos_B = triple["gem_B_pos"]

        dist_B = math.hypot(zustand.bot.x - pos_B.x, zustand.bot.y - pos_B.y)
        signal_B = calculate_signal(dist_B, zustand)

        sig_C_expected = current_residual - signal_A - signal_B

        # Neue Kandidaten für C berechnen
        new_candidates_C = get_candidates_for_residual(zustand, sig_C_expected)

        # Schnittmenge mit den alten C-Kandidaten dieser Hypothese bilden
        intersection_C = triple["gem_C_candidates"].intersection(new_candidates_C)

        if len(intersection_C) > 0:
            # Diese Hypothese lebt noch!
            triple["gem_C_candidates"] = intersection_C
            pos_As.add(pos_A)
            pos_Bs.add(pos_B)
            pos_Cs |= intersection_C
            valid_triples.append(triple)
    zustand.current_candidates = pos_As

    zustand.possible_triples = valid_triples
    # Check: Haben wir es gelöst?
    if len(pos_As) == 1:
        final_A = list(pos_As)[0]
        new_gem_data_A = {
            "position": [final_A.x, final_A.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - zustand.discovered_in_tick_A),
        }
        new_gem_obj_A = Gem(**new_gem_data_A)
        zustand.remembered_gems.append(new_gem_obj_A)
        to_pair = []
        for triple in zustand.possible_triples:
            to_pair.append(
                {
                    "gem_A_pos": triple["gem_B_pos"],
                    "gem_B_candidates": triple["gem_C_candidates"],
                }
            )
        zustand.possible_pairs = to_pair
        zustand.possible_triples = []
    if len(pos_Bs) == 1:
        final_B = list(pos_Bs)[0]
        new_gem_data_B = {
            "position": [final_B.x, final_B.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - zustand.discovered_in_tick_B),
        }
        new_gem_obj_B = Gem(**new_gem_data_B)
        zustand.remembered_gems.append(new_gem_obj_B)
        to_pair = []
        for triple in zustand.possible_triples:
            to_pair.append(
                {
                    "gem_A_pos": triple["gem_A_pos"],
                    "gem_B_candidates": triple["gem_C_candidates"],
                }
            )
        zustand.possible_pairs = to_pair
        zustand.possible_triples = []

    if len(pos_Cs) == 1:
        final_C = list(pos_Cs)[0]
        new_gem_data_C = {
            "position": [final_C.x, final_C.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - zustand.discovered_in_tick_C),
        }
        new_gem_obj_C = Gem(**new_gem_data_C)
        zustand.remembered_gems.append(new_gem_obj_C)
        to_pair = []
        for triple in zustand.possible_triples:
            candidates = set()
            candidates.add(triple["gem_B_pos"])
            to_pair.append(
                {"gem_A_pos": triple["gem_A_pos"], "gem_B_candidates": candidates}
            )
        zustand.possible_pairs = to_pair
        zustand.possible_triples = []

    if (
        len(zustand.possible_triples) == 1
        and len(zustand.possible_triples[0]["gem_C_candidates"]) == 1
    ):
        # BINGO! Beide gefunden.
        final_A = zustand.possible_triples[0]["gem_A_pos"]
        final_B = zustand.possible_triples[0]["gem_B_pos"]
        final_C = list(zustand.possible_triples[0]["gem_C_candidates"])[0]
        new_gem_data_A = {
            "position": [final_A.x, final_A.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - zustand.discovered_in_tick_A),
        }
        new_gem_obj_A = Gem(**new_gem_data_A)
        zustand.remembered_gems.append(new_gem_obj_A)

        new_gem_data_B = {
            "position": [final_B.x, final_B.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - (zustand.discovered_in_tick_B)),
        }
        new_gem_obj_B = Gem(**new_gem_data_B)
        zustand.remembered_gems.append(new_gem_obj_B)

        new_gem_data_C = {
            "position": [final_C.x, final_C.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - (zustand.discovered_in_tick_C)),
        }
        new_gem_obj_C = Gem(**new_gem_data_C)
        zustand.remembered_gems.append(new_gem_obj_C)

        zustand.possible_triples = []


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


def check_possible_duos(zustand: Zustand):
    valid_duos = []
    known = get_signal_from_known_gems(zustand)
    current_residual = zustand.signal_level - known
    pos_As = set()
    pos_Bs = set()

    for duo in zustand.possible_duos:
        pos_A = duo[0]

        if pos_A in zustand.floors:
            continue

        if zustand.saved_matrix[pos_A.y][pos_A.x] == "X":
            continue

        dist = math.hypot(zustand.bot.x - pos_A.x, zustand.bot.y - pos_A.y)
        signal_A = calculate_signal(dist, zustand)

        sig_B_expected = current_residual - signal_A

        # Neue Kandidaten für B berechnen
        new_candidates_B = get_candidates_for_residual(zustand, sig_B_expected)

        # Schnittmenge mit den alten B-Kandidaten dieser Hypothese bilden
        if duo[1] in new_candidates_B:
            pos_As.add(pos_A)
            pos_Bs.add(duo[1])
            valid_duos.append(duo)

    zustand.current_candidates = pos_As

    zustand.possible_duos = valid_duos
    if len(zustand.possible_duos) == 1:
        # BINGO! Beide gefunden.
        final_A = zustand.possible_duos[0][0]
        final_B = zustand.possible_duos[0][1]
        new_gem_data_A = {
            "position": [final_A.x, final_A.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - zustand.discovered_in_tick_A),
        }
        new_gem_obj_A = Gem(**new_gem_data_A)
        zustand.remembered_gems.append(new_gem_obj_A)

        new_gem_data_B = {
            "position": [final_B.x, final_B.y],
            "ttl": zustand.config.gem_ttl
            - (zustand.tick - zustand.discovered_in_tick_B),
        }
        new_gem_obj_B = Gem(**new_gem_data_B)
        zustand.remembered_gems.append(new_gem_obj_B)
        zustand.possible_duos = []


def resolve_two_unknown_gems(zustand: Zustand):
    """
    Findet alle Paare von Positionen, die zusammen exakt das Zielsignal ergeben.
    """
    width = zustand.config.width
    height = zustand.config.height
    target_residual_signal = zustand.signal_level - get_signal_from_known_gems(zustand)

    # 1. Lookup-Table aufbauen: Signal -> Liste von Positionen
    # Key: Signal (gerundet auf 5 Stellen), Value: Liste von (x,y)
    signal_map = defaultdict(list)
    valid_floors = []

    # Iteriere über alle begehbaren Felder
    for y in range(height):
        for x in range(width):
            if zustand.saved_matrix[y][x] != "X":
                pos = (x, y)
                dist = math.hypot(x - zustand.bot.x, y - zustand.bot.y)
                sig = calculate_signal(dist, zustand)

                # Wir runden, um Floating-Point Ungenauigkeiten abzufangen
                sig_key = round(sig, 5)

                # Nur relevante Signale speichern (Signal > 0)
                if sig_key > 0:
                    signal_map[sig_key].append(pos)
                    # signal und Positionen, die das hervorrufen
                    valid_floors.append((pos, sig_key))
                    # Pos hat genau das Signal in sig_key

    possible_solutions = set()

    # 2. Matching: Iteriere durch alle möglichen 'Ersten' Gems
    for pos1, sig1 in valid_floors:

        # Wie viel Signal muss der zweite Gem liefern?
        needed_sig = target_residual_signal - sig1
        needed_key = round(needed_sig, 5)

        # Haben wir Kandidaten für dieses Rest-Signal?
        if needed_key in signal_map:
            candidates_pos2 = signal_map[needed_key]

            for pos2 in candidates_pos2:
                # Duplikate vermeiden: Wir speichern nur wenn pos1 <= pos2
                # (verhindert, dass wir (A,B) und (B,A) doppelt speichern)
                if pos1 <= pos2:
                    if pos1 == pos2:
                        continue

                    # Lösung gefunden!
                    sol = tuple((Position(pos1), Position(pos2)))
                    possible_solutions.add(sol)

    # Rückgabe: Ein Set von Tupeln.
    return possible_solutions
