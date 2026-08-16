import math

from include.highlighting import debug_print
from include.signal_interpreter import (
    get_candidates_for_signal,
    get_fade_by_tick,
    get_signal_from_gem,
)
from include.zustand import Zustand


def handle_gems(zustand: Zustand):
    """Aktualisiert die Informationen über Gems basierend auf der aktuellen Tick-Information."""
    gems_to_remove = []
    for gem in zustand.remembered_gems:
        gem.ttl -= 1
        if gem.ttl == 0:
            gems_to_remove.append(gem)

    for gem in gems_to_remove:
        if gem.channel != -1:
            zustand.discovered_in_tick[gem.channel] = -1
            zustand.candidates[gem.channel] = set()
        zustand.remembered_gems.remove(gem)

    all_gem_pos = []
    for gem in zustand.remembered_gems:
        all_gem_pos.append(gem.position)

    # Gems entfernen, die nicht mehr erreichbar sind
    reachable_remembered = []
    for gem in zustand.remembered_gems:
        if gem.position in zustand.distances_to_bot:
            if zustand.distances_to_bot[gem.position] is not None:
                reachable_remembered.append(gem)
        else:
            if zustand.config.max_gems > gem.channel >= 0:
                zustand.candidates[gem.channel] = set()
    zustand.remembered_gems = reachable_remembered

    # gems entfernen, deren Kanal 0 ist
    # bzw. deren Signal nicht mit dem auf dem Kanal übereinstimmt

    still_there = []
    for channel in range(zustand.config.max_gems):
        if zustand.reseted_channels[channel] != ():
            if zustand.tick - zustand.reseted_channels[channel][1] < 3:
                continue
            else:
                zustand.reseted_channels[channel] = ()
        else:
            zustand.reseted_channels[channel] = ()
    for gem in zustand.remembered_gems:
        if gem.channel != -1:
            if abs(zustand.signal_channels[gem.channel]) > 0.0:
                fade_multiplier = get_fade_by_tick(
                    zustand, zustand.discovered_in_tick[gem.channel]
                )
                allowed_diff = (
                    zustand.config.signal_noise * 1 / math.sqrt(3) * 5
                ) * fade_multiplier
                predicted_signal = get_signal_from_gem(zustand, gem)
                zustand.candidates[gem.channel] = set()

                if (
                    abs(zustand.signal_channels[gem.channel] - predicted_signal)
                    <= allowed_diff
                ):
                    still_there.append(gem)
                else:
                    zustand.candidates[gem.channel] = set()
                    zustand.reseted_channels[gem.channel] = [gem.position, zustand.tick]
            else:
                zustand.discovered_in_tick[gem.channel] = -1
                zustand.candidates[gem.channel] = set()
        else:
            still_there.append(gem)
    zustand.remembered_gems = still_there

    # Gems entfernen, weil der Bot drauf steht
    new_remembered = []
    for gem in zustand.remembered_gems:
        if zustand.bot == gem.position:
            if gem.channel != -1:
                zustand.candidates[gem.channel] = set()
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
            else:
                if zustand.config.max_gems > remembered_gem.channel >= 0:
                    zustand.candidates[remembered_gem.channel] = set()
            # sonst: nicht hinzufügen (wird entfernt)
        else:
            # nicht auf dem Floor -> behalten
            new_remembered.append(remembered_gem)
    zustand.remembered_gems = new_remembered

    # Visible Gems einfügen mit korrektem Kanal
    ticks_with_channel = {}
    for i in range(zustand.config.max_gems):
        key = zustand.discovered_in_tick[i]
        ticks_with_channel[key] = i

    for v_gem in zustand.visible_gems:
        known = False
        for r_gem in zustand.remembered_gems:
            if v_gem.position == r_gem.position:
                known = True
                break
        if known == False:
            spawn_tick = zustand.tick - (zustand.config.gem_ttl - v_gem.ttl)
            if spawn_tick == zustand.tick:
                for index in range(zustand.config.max_gems):
                    if (
                        zustand.last_signal_channels[index] == 0
                        and zustand.signal_channels[index] > 0
                    ):
                        channel = index
                        v_gem.channel = channel
                        zustand.discovered_in_tick[index] = zustand.tick
                        zustand.candidates[channel] = set()
                        zustand.remembered_gems.append(v_gem)
                        break

            elif spawn_tick in set(ticks_with_channel.keys()):
                channel = ticks_with_channel[spawn_tick]
                v_gem.channel = channel
                zustand.candidates[channel] = set()
                zustand.remembered_gems.append(v_gem)
            else:
                keys = ticks_with_channel.keys()
                least_diff = 500
                best_key = None
                for key in keys:
                    if spawn_tick <= key and key - spawn_tick < least_diff:
                        least_diff = key - spawn_tick
                        best_key = key
                channel = ticks_with_channel[best_key]
                v_gem.channel = channel
                zustand.candidates[channel] = set()
                zustand.remembered_gems.append(v_gem)


def track_points(zustand: Zustand):
    """Aktualisiert die Punkte des Bots und des Gegners basierend auf den gesammelten Gems."""
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
            and zustand.config.gem_ttl
            - (zustand.tick - zustand.discovered_in_tick[index])
            != points - 1
            and zustand.discovered_in_tick[index] > -1
            and zustand.config.gem_ttl
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
                # Signal Obergrenze und Untergrenze bestimmen und clampen
                real_signal_min = max(
                    0,
                    (
                        (
                            zustand.last_signal_channels[index]
                            - zustand.weights.s_error_margin
                        )
                        / fade_multiplier
                    ),
                )
                real_signal_max = min(
                    1,
                    (
                        (
                            zustand.last_signal_channels[index]
                            + zustand.weights.s_error_margin
                        )
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
    zustand.last_hypothetical_gems = zustand.hypothetical_gems.copy()
    zustand.last_signal_channels = zustand.signal_channels.copy()

    zustand.last_move = move
    zustand.last_opponent = zustand.opponent
    zustand.last_bot = zustand.bot


def connect_portals(zustand: Zustand):
    """Trägt die Mid-Portale mit den Border-Portalen zusammen, um die Teleportationsinformationen zu aktualisieren."""
    unconected_index = len(zustand.portal_pairs)
    unconected_mid_portals = zustand.mid_portals[unconected_index:]
    unconected_border_portals = zustand.border_portals[unconected_index:]
    while len(unconected_mid_portals) > 0 and len(unconected_border_portals) > 0:

        mid_portal = unconected_mid_portals.pop(0)
        border_portal = unconected_border_portals.pop(0)

        zustand.portal_pairs.append((mid_portal, border_portal))

        zustand.portal_teleportations.update({mid_portal[0]: border_portal[1]})
        zustand.portal_teleportations.update({border_portal[0]: mid_portal[1]})

        # (From E1 to E2): P1
        for neighbour in get_neighbours(zustand, mid_portal[0]):
            zustand.e_e_p.update({(neighbour, border_portal[1]): mid_portal[0]})
        for neighbour in get_neighbours(zustand, border_portal[0]):
            zustand.e_e_p.update({(neighbour, mid_portal[1]): border_portal[0]})


def get_neighbours(zustand: Zustand, pos: tuple):
    """Gibt die benachbarten Felder zurück, die nicht von einer Wand blockiert sind."""
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    for dx, dy in directions:
        nx, ny = pos[0] + dx, pos[1] + dy
        if (
            0 <= nx < len(zustand.saved_matrix[0])
            and 0 <= ny < len(zustand.saved_matrix)
            and zustand.saved_matrix[ny][nx] != "X"
        ):
            yield (nx, ny)


def save_opponent_portals(zustand: Zustand):
    if zustand.went_through == True:
        move_dict = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}
        offset = move_dict[zustand.last_move]
        portal = (zustand.last_bot[0] + offset[0], zustand.last_bot[1] + offset[1])
        zustand.portal_teleportations.update({portal: zustand.bot})

        for neighbour in get_neighbours(zustand, portal):
            zustand.e_e_p.update({(neighbour, zustand.bot): portal})

        zustand.solved_opponent_portals.append(portal)

    zustand.went_through = False
