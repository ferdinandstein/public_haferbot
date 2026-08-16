import math

from include.buffer import (
    remove_channel_from_buffer,
    write_new_gem_msg,
)
from include.highlighting import debug_print
from include.signal_interpreter import (
    get_signal_from_gem,
)
from include.zustand import Zustand


def handle_gems(zustand: Zustand):
    """Aktualisiert die Informationen über Gems basierend auf der aktuellen Tick-Information."""

    # Abgelaufene Gems entfernen
    gems_to_remove = []
    for gem in zustand.remembered_gems:
        gem.ttl -= 1
        if gem.ttl == 0:
            gems_to_remove.append(gem)

    for gem in gems_to_remove:
        if gem.channel != -1:
            zustand.candidates[gem.channel] = set()
            remove_channel_from_buffer(gem.channel, zustand)
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
                remove_channel_from_buffer(gem.channel, zustand)
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
                allowed_diff = 0.001
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
                zustand.candidates[gem.channel] = set()
        else:
            still_there.append(gem)
    zustand.remembered_gems = still_there

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
                if remembered_gem.channel >= 0:
                    zustand.candidates[remembered_gem.channel] = set()
                    if remembered_gem.channel != -1:
                        remove_channel_from_buffer(remembered_gem.channel, zustand)
            # sonst: nicht hinzufügen (wird entfernt)
        else:
            # nicht auf dem Floor -> behalten
            new_remembered.append(remembered_gem)
    zustand.remembered_gems = new_remembered

    # Remembered Gems Kanal geben, wenn sie keinen haben.
    for remembered_gem in zustand.remembered_gems:
        if remembered_gem.channel == -1:
            expected_signal = get_signal_from_gem(zustand, remembered_gem)
            best_channel = -1
            min_diff = float("inf")
            for channel_idx, signal_value in enumerate(zustand.signal_channels):
                if signal_value == 0.0:
                    continue
                diff = abs(signal_value - expected_signal)
                if diff < min_diff and diff < 0.001:
                    min_diff = diff
                    best_channel = channel_idx
            if best_channel != -1:
                remembered_gem.channel = best_channel
                write_new_gem_msg(remembered_gem, zustand)

    # Visible Gems einfügen mit korrektem Kanal
    visible_gems_to_process = []
    blocked_channels = set()

    for r_gem in zustand.remembered_gems:
        blocked_channels.add(r_gem.channel)

    for gem in zustand.visible_gems:
        if gem.type_ == "swarm":
            zustand.gems_and_nodes[gem.position] = gem.nodes
        known_match = None
        for r_gem in zustand.remembered_gems:
            if gem.position == r_gem.position:
                known_match = r_gem
                r_gem.type_ = gem.type_
                r_gem.ttl = gem.ttl

                gem.channel = r_gem.channel
                debug_print(
                    f"Gem at {gem.position} is already known, updating ttl to {gem.ttl} and type to {gem.type_}, Channel: {r_gem.channel}.",
                    zustand,
                )
                write_new_gem_msg(gem, zustand)
                break

        if known_match:
            known_match.ttl = gem.ttl
            blocked_channels.add(known_match.channel)
        else:
            visible_gems_to_process.append(gem)

    for new_gem in visible_gems_to_process:
        best_channel = -1
        min_diff = float("inf")

        expected_signal = get_signal_from_gem(zustand, new_gem)

        # Besten Kanal bestimmen

        for channel_idx, signal_value in enumerate(zustand.signal_channels):

            if channel_idx in blocked_channels:
                continue
            if signal_value == 0.0:
                continue

            diff = abs(signal_value - expected_signal)

            if diff < min_diff and diff < 0.001:
                min_diff = diff
                best_channel = channel_idx
        if best_channel != -1:
            new_gem.channel = best_channel
            age = zustand.config.gem_ttl - new_gem.ttl
            spawn_tick = zustand.tick - age
            zustand.discovered_in_tick[best_channel] = spawn_tick

            zustand.candidates[best_channel] = set()
            zustand.remembered_gems.append(new_gem)
            blocked_channels.add(best_channel)
            debug_print(
                f"Found new gem at {new_gem.position} through vision, writing it in buffer.",
                zustand,
            )
            write_new_gem_msg(new_gem, zustand)

        else:
            zustand.remembered_gems.append(new_gem)


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


def set_last_vars(zustand: Zustand, move):
    """Variablen von diesem Tick für nächsten Tick speichern"""
    zustand.last_remembered_gems = zustand.remembered_gems.copy()
    zustand.last_visible_gems = zustand.visible_gems.copy()
    zustand.last_hypothetical_gems = zustand.hypothetical_gems.copy()
    zustand.last_signal_channels = zustand.signal_channels.copy()

    zustand.last_move = move
    zustand.last_bot = zustand.bot
    zustand.last_last_bot = zustand.last_bot
