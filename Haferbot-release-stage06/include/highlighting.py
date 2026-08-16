# Datei mit Funktionen zum Debuggen und highlighten

import math
import os
from include.zustand import Zustand
import sys
import time
import uuid


def debug_print(message, zustand: Zustand):
    if zustand.debug_enabled and zustand.config.bot_id in [0, 1]:
        colors = [94, 91, 92, 93]
        if os.name == "posix":
            print(
                f"\x1b[1;{colors[zustand.config.bot_id]}m{message}\x1b[0m",
                file=sys.stderr,
            )
        else:
            print(
                f"\x1b[1;{colors[zustand.config.bot_id]}m{message}\x1b[0m",
                file=sys.stderr,
            )


def highlight_matrix(matrix, zustand: Zustand):
    highlight_items = []
    if zustand.debug_enabled == True:
        y = 0
        for row in matrix:
            x = 0
            for item in row:
                if item == "0":
                    converted_item = [x, y, "#00dd0041"]
                    highlight_items.append(converted_item)

                if item == "X":
                    converted_item = [x, y, "#ff00156c"]
                    highlight_items.append(converted_item)
                x += 1
            y += 1
    return highlight_items


def highlight_path(zustand: Zustand):
    highlight_items = []
    path_positions = zustand.a_star_path
    if zustand.debug_enabled == True and path_positions is not None:
        for position in path_positions:
            converted_item = [position[0], position[1], "#2018fc72"]
            highlight_items.append(converted_item)

    return highlight_items


def highlight_gems(gems, zustand: Zustand):
    highlight_items = []
    if zustand.debug_enabled == True and len(gems) != 0:
        for gem in gems:
            converted_item = [gem.position[0], gem.position[1], "#e918fcff"]
            highlight_items.append(converted_item)

    return highlight_items


def highlight_candidates(zustand: Zustand):
    highlight_items = []
    colors = [
        "#fffb00",
        "#ffbb00",
        "#FF5E00",
        "#ff0000",
        "#24bc02",
        "#00bfff",
        "#4000ff",
    ]

    if zustand.debug_enabled == True:
        i = 0
        for channel in zustand.candidates:
            if len(channel) > 0:
                for tile in channel:
                    converted_item = [tile[0], tile[1], colors[i % len(colors)]]
                    highlight_items.append(converted_item)
            i += 1

    return highlight_items


def print_message(zustand: Zustand):
    if (
        zustand.config.bot_id == 0
        and zustand.messaged == False
        and zustand.opponent_emoji != ""
    ):
        zustand.messaged = True
        print(
            "\x1b[1m\x1b[38;5;73m#############################",
            file=sys.stderr,
            flush=True,
        )
        try:
            if zustand.opponent_emoji in zustand.messages:
                print(
                    f"\x1b[1m\x1b[38;5;73m{zustand.messages[zustand.opponent_emoji]}",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(
                    f"\x1b[1m\x1b[38;5;73mHallo {zustand.opponent_emoji}!",
                    file=sys.stderr,
                    flush=True,
                )
        except (KeyError, TypeError, UnicodeError):
            print(
                f"\x1b[1m\x1b[38;5;73mHallo!",
                file=sys.stderr,
                flush=True,
            )
        print(
            "\x1b[1m\x1b[38;5;73m#############################",
            file=sys.stderr,
            flush=True,
        )


def print_stats(
    zustand: Zustand, max_tick_time: float, max_buffer_usage, all_buffer_usages
):
    if zustand.tick == zustand.config.max_ticks - 1:

        debug_print(f"Max Tick Time: {max_tick_time:0.2f}ms", zustand)
        debug_print(f"Max Buffer Usage: {max_buffer_usage}/256", zustand)
        debug_print(
            f"AVG Buffer Usage: {(sum(all_buffer_usages)/len(all_buffer_usages)):0.2f}/256",
            zustand,
        )
        debug_print(f"Min Bits per Point {min(zustand.bits_per_point)}", zustand)
        debug_print(
            f"AVG Bits per Point {sum(zustand.bits_per_point)/len(zustand.bits_per_point)}",
            zustand,
        )


def print_log(zustand: Zustand, tick_time: float, command: dict):
    if (
        zustand.debug_enabled
        and (time.perf_counter_ns() - zustand.start_time) / 1000000 > 1500
    ):
        top = 0
        diff = 0
        for item in zustand.run_time_analyse:
            if (
                item[0] == "write_zustand"
                or item[0] == "get_route_by_permutations_for_bot"
                or item[0] == "generate_a_star_path"
            ):
                top += item[1]
                debug_print(
                    f"{item[0]}: {item[1]}ms (diff: {(item[1] - diff):.2f}ms)",
                    zustand,
                )
                diff = 0
            else:
                diff += item[1]
                if len(item) > 2:
                    debug_print(
                        f"---{item[0]}: {item[1]}ms (count: {item[2]})", zustand
                    )
                else:
                    debug_print(f"---{item[0]}: {item[1]}ms", zustand)

        debug_print(f"Write Zustand + Route + Astar: {top:.2f}ms", zustand)
        debug_print(f"Total Tick Time: {tick_time}ms", zustand)
        debug_print(f"Differenz: {(tick_time - top):.2f}ms", zustand)
        command.update({"command": "pause"})

    return command


def get_highlight_items(zustand: Zustand):
    if zustand.debug_enabled == True and (
        sys.platform == "win32"
        or (uuid.getnode() == 9619529777783)
        or (uuid.getnode() == 256017930633619)
    ):
        highlight_items = (
            # highlight_matrix(zustand.shared_matrix, zustand)
            highlight_path(zustand)
            # + highlight_gems(zustand.remembered_gems, zustand)
            # + highlight_candidates(zustand)
            # + highlight_gems(zustand.hypothetical_gems, zustand)
            # + highlight_opponent(zustand)
            + highlight_buffer_gems(zustand)
            + highlight_nodes(zustand)
            + highlight_teammates(zustand)
        )
    else:
        highlight_items = []
    return highlight_items


def highlight_nodes(zustand: Zustand):
    highlight_items = []
    for nodes in zustand.gems_and_nodes.values():
        for node in nodes:
            highlight_items.append([node[0], node[1], "#f4e006ff"])
    return highlight_items


def highlight_teammates(zustand: Zustand):
    highlight_items = []
    for t in zustand.teammates:
        highlight_items.append([t[0], t[1], "#06f495ff"])
    return highlight_items


def highlight_buffer_gems(zustand: Zustand):
    highlight_items = []
    if zustand.debug_enabled == True and len(zustand.gems_in_buffer) != 0:
        for gem in zustand.gems_in_buffer:
            if gem.type_ == "swarm":
                color = "#e918fcff"
            else:
                color = "#00e5ffff"
            converted_item = [gem.position[0], gem.position[1], color]
            highlight_items.append(converted_item)

    return highlight_items
