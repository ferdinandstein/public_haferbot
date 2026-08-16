import math

from include.highlighting import debug_print
from include.signal_interpreter import (
    get_candidates_for_signal,
    get_fade_by_tick,
)
from include.zustand import Zustand


def handle_gems(zustand: Zustand):
    all_gem_pos = []
    for gem in zustand.remembered_gems:
        all_gem_pos.append(gem.position)

    # Gems entfernen, die nicht mehr erreichbar sind
    reachable_remembered = []
    for gem in zustand.remembered_gems:
        if gem.position in zustand.distances_to_bot:
            if zustand.distances_to_bot[gem.position] is not None:
                reachable_remembered.append(gem)
    zustand.remembered_gems = reachable_remembered

    # Gems entfernen, weil der Bot drauf steht
    new_remembered = []
    for gem in zustand.remembered_gems:
        if zustand.bot == gem.position:
            least = 5000
            spawn_tick = zustand.tick - (zustand.config.gem_ttl - gem.ttl)
            for spawn in zustand.spawn_ticks:
                if abs(spawn - spawn_tick) < least:
                    least = abs(spawn - spawn_tick)
                    index = zustand.spawn_ticks.index(spawn)
            zustand.spawn_ticks[index] = -1
            pass
        else:
            new_remembered.append(gem)
    zustand.remembered_gems = new_remembered

    # Entfernen von Gems, die nicht mehr da sind,
    # weil vom Gegner geklaut wurden oder abgelaufen sind
    new_remembered = []
    for remembered_gem in zustand.remembered_gems:
        if remembered_gem.position in zustand.floors:
            # Der remembered_gem ist auf dem Floor,
            # prüfen, ob das Gem noch in visible_gems ist
            is_still_there = False
            for visible_gem in zustand.visible_gems:
                if remembered_gem.position == visible_gem.position:
                    is_still_there = True
                    break
            if is_still_there == True:
                new_remembered.append(remembered_gem)
            # sonst: nicht hinzufügen (wird entfernt)
        else:
            # nicht auf dem Floor -> behalten
            new_remembered.append(remembered_gem)
    zustand.remembered_gems = new_remembered

    # Visible Gems einfügen
    for v_gem in zustand.visible_gems:
        known = False
        least_dist = 1000
        twin = None
        for r_gem in zustand.remembered_gems:
            dist = abs(v_gem.position[0] - r_gem.position[0]) + abs(
                v_gem.position[1] - r_gem.position[1]
            )
            if dist < least_dist:
                least_dist = dist
                twin = r_gem
            if v_gem.position == r_gem.position:
                known = True
                break
        if known == False:
            if least_dist <= 7:
                zustand.remembered_gems.remove(twin)
            zustand.remembered_gems.append(v_gem)


def track_points(zustand: Zustand):
    if zustand.tick == 0:
        return
    points = 0
    for l_gem in zustand.last_visible_gems:
        if l_gem.position == zustand.bot:
            zustand.my_points += l_gem.ttl
            points = l_gem.ttl
            break

    for index in range(zustand.config.max_gems):
        if (
            zustand.last_signal_channels[index] != 0
            and zustand.signal_channels[index] == 0
        ):
            if (
                zustand.config.gem_ttl
                - (zustand.tick - zustand.discovered_in_tick[index])
                != points - 1
                and zustand.discovered_in_tick[index] > -1
            ):
                if (
                    zustand.config.gem_ttl
                    - (zustand.tick - zustand.discovered_in_tick[index])
                    > 0
                ):
                    zustand.opponent_points += (
                        zustand.config.gem_ttl
                        - (zustand.tick - zustand.discovered_in_tick[index])
                        + 1
                    )
                    if zustand.candidates[index]:
                        zustand.opponent_area = zustand.candidates[index]
                    else:
                        fade_multiplier = get_fade_by_tick(
                            zustand, zustand.discovered_in_tick[index] + 1
                        )
                        factor = 1 / math.sqrt(3)
                        sigma_step = zustand.config.signal_noise * factor
                        error_margin = sigma_step * 3
                        # Signal Obergrenze und Untergrenze bestimmen und clampen
                        real_signal_min = max(
                            0,
                            (
                                (zustand.last_signal_channels[index] - error_margin)
                                / fade_multiplier
                            ),
                        )
                        real_signal_max = min(
                            1,
                            (
                                (zustand.last_signal_channels[index] + error_margin)
                                / fade_multiplier
                            ),
                        )
                        step_candidates = get_candidates_for_signal(
                            zustand, real_signal_min, real_signal_max
                        )
                        zustand.opponent_area = step_candidates


def track_opponent(zustand: Zustand):
    if zustand.opponent_area:
        new_area = set()
        for pos in zustand.opponent_area:

            if zustand.saved_matrix[pos[1]][pos[0]] == "X":
                continue
            if pos not in zustand.floors:
                new_area.add(pos)
            directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
            for x, y in directions:
                nx, ny = pos[0] + x, pos[1] + y
                if zustand.saved_matrix[ny][nx] == "X":
                    continue
                if (nx, ny) in zustand.floors:
                    continue
                new_area.add((nx, ny))
        zustand.opponent_area = new_area


def set_last_vars(zustand: Zustand, move):
    zustand.last_remembered_gems = zustand.remembered_gems.copy()
    zustand.last_visible_gems = zustand.visible_gems.copy()

    zustand.last_move = move
    zustand.last_opponent = zustand.opponent

    zustand.last_antennas = zustand.antennas.copy()
    zustand.last_signal = zustand.signal_level
    zustand.dictionary_of_signals_and_stuff.update(
        {
            zustand.tick: {
                "level_bot": zustand.signal_level,
                "antennas": zustand.antennas,
                "candidates": zustand.candidates,
                "possible_pairs": zustand.possible_pairs,
                "remembered_gems": zustand.remembered_gems,
            }
        }
    )


def track_gem_count(zustand: Zustand):
    if zustand.signal_level == 0:
        return

    for l_gem in zustand.last_visible_gems:
        if l_gem.position == zustand.bot:
            gem_eaten = True
            break
    else:
        gem_eaten = False

    if zustand.tick > 2:
        last_antennas = zustand.dictionary_of_signals_and_stuff[zustand.tick - 2][
            "antennas"
        ]
    else:
        last_antennas = zustand.last_antennas
    antenna_diffs = []
    for antenna in zustand.antennas:
        for l_antenna in last_antennas:
            if antenna.position == l_antenna.position:
                antenna_diffs.append(
                    [antenna.signal - l_antenna.signal, antenna.signal]
                )
                break

    if len(antenna_diffs) == 0:
        return

    max_diff = -100
    raw_signal = 1
    for diff in antenna_diffs:
        if diff[0] > max_diff:
            max_diff = diff[0]
            raw_signal = diff[1]

    if gem_eaten == True and max_diff < -0.8:
        debug_print("Gem eaten and no new spawned", zustand)
    elif max_diff > 4 * zustand.config.signal_noise:
        debug_print(f"###New Gem found in Tracking### in Tick {zustand.tick}", zustand)
        # if zustand.spawn_ticks[1] != -1:
        #    zustand.spawn_ticks[1] = zustand.tick - 2
        # else:
        #    zustand.spawn_ticks[0] = zustand.tick - 2
        # debug_print(f"###Tracking Candidates### from Tick {zustand.tick -3}", zustand)
        # zustand.candidates = zustand.dictionary_of_signals_and_stuff[zustand.tick - 3][
        #    "candidates"
        # ]
