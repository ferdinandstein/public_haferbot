import math

from include.zustand import Zustand
import sys


def debug_print(message, zustand: Zustand):
    if zustand.debug_enabled:
        print("\x1b[1;38;5;73m" + message, file=sys.stderr, flush=True)


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
            converted_item = [position[0], position[1], "#2018fcff"]
            highlight_items.append(converted_item)

    return highlight_items


def highlight_gems(gems, zustand: Zustand):
    highlight_items = []
    if zustand.debug_enabled == True and len(gems) != 0:
        for gem in gems:
            converted_item = [gem.position[0], gem.position[1], "#e918fcff"]
            highlight_items.append(converted_item)

    return highlight_items


def highlight_frontiers(frontiers, zustand: Zustand):
    highlight_items = []
    frontier_positions = frontiers
    if zustand.debug_enabled == True and frontier_positions is not None:
        for position in frontier_positions:
            converted_item = [position[0], position[1], "#18defcff"]
            highlight_items.append(converted_item)

    return highlight_items


def highlight_clusters(zustand: Zustand):
    highlight_items = []
    clusters_with_mid = zustand.clusters
    if zustand.debug_enabled == True and clusters_with_mid is not None:
        colors = [
            "#fffb00",
            "#0000ff",
            "#00ffff",
            "#ff00ff",
        ]
        # for c_id, cluster_with_mid in enumerate(clusters_with_mid):
        #    cluster = cluster_with_mid[0]
        #    mid = cluster_with_mid[1]
        #    color = colors[c_id % len(colors)]

        #    for position in cluster:
        #        converted_item = [position[0], position[1], color]
        #        highlight_items.append(converted_item)

        for y in range(zustand.config.height):
            for x in range(zustand.config.width):
                if zustand.current_matrix[y][x] == "/":
                    if zustand.dictionary_of_all_tiles[(x, y)]["owner"] is not None:
                        color = colors[
                            zustand.dictionary_of_all_tiles[(x, y)]["owner"]
                            % len(colors)
                        ]
                        converted_item = [
                            x,
                            y,
                            color,
                        ]
                        highlight_items.append(converted_item)
        idx = 0
        for cluster_with_mid in zustand.clusters:
            mid = cluster_with_mid[1]
            converted_item = [mid[0], mid[1], colors[(idx + 1) % len(colors)]]
            highlight_items.append(converted_item)
            idx += 1

        # converted_item = [mid[0], mid[1], "#ffffffc1"]
        # highlight_items.append(converted_item)

    return highlight_items


def highlight_fov(visible, zustand: Zustand):
    if len(visible) == 0:
        return []
    highlight_items = []

    if zustand.debug_enabled == True and visible is not None:

        for tile in visible:
            try:
                converted_item = [tile[0], tile[1], "#fc1818ff"]
                highlight_items.append(converted_item)
            except Exception as e:
                pass

    return highlight_items


def highlight_dicts_lst(zustand: Zustand):
    highlight_items = []

    if zustand.debug_enabled:
        max_diff = 200  # ab hier volle Farbe

        for tile in zustand.dictionary_of_all_tiles.items():

            position, info = tile
            diff = zustand.tick - info["LST"]
            diff = min(diff, max_diff)

            t = diff / max_diff  # 0..1

            r = int(255 * t)
            g = 0
            b = int(255 * (1 - t))

            colour = (r << 16) | (g << 8) | b
            converted_item = [position[0], position[1], f"#{colour:06X}"]
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
                    converted_item = [tile[0], tile[1], colors[i]]
                    highlight_items.append(converted_item)
            i += 1

    return highlight_items


def print_message(zustand: Zustand):
    if (
        zustand.messaged == False
        and zustand.opponent_emoji != ""
        and zustand.tick > 100
    ):
        zustand.messaged = True
        print(
            "##########################################",
            file=sys.stderr,
            flush=True,
        )
        try:
            if zustand.opponent_emoji in zustand.messages:
                print(
                    zustand.messages[zustand.opponent_emoji],
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(
                    f"Hallo {zustand.opponent_emoji}!",
                    file=sys.stderr,
                    flush=True,
                )
        except (KeyError, TypeError, UnicodeError):
            print(
                f"Hallo!",
                file=sys.stderr,
                flush=True,
            )
        print(
            "##########################################",
            file=sys.stderr,
            flush=True,
        )


def print_stats(zustand: Zustand, max_tick_time: float):
    if zustand.tick == zustand.config.max_ticks - 1:

        if zustand.with_opponent:
            if zustand.my_points >= zustand.opponent_points:
                verb = "gewonnen 🥳"
                print(
                    f"Ich habe mit {zustand.my_points} zu {zustand.opponent_points} Punkten {verb}",
                    flush=True,
                    file=sys.stderr,
                )
            else:
                verb = "verloren 😞"
                print(
                    f"Ich habe mit {zustand.my_points} zu {zustand.opponent_points} Punkten {verb}",
                    flush=True,
                    file=sys.stderr,
                )

        else:
            print(
                f"Score: {zustand.my_points}",
                flush=True,
                file=sys.stderr,
            )

        debug_print(
            f"Gem-Utilization ≈ {math.floor((zustand.my_points/zustand.total_gems_ttl)*10000)/100}%",
            zustand,
        )

        debug_print(f"Max Tick Time: {max_tick_time:0.2f}ms", zustand)


def highlight_opponent(zustand: Zustand):
    highlight_items = []

    if zustand.debug_enabled == True and zustand.opponent_area:

        for pos in zustand.opponent_area:
            converted_item = [pos[0], pos[1], "#00eeff"]
            highlight_items.append(converted_item)

    return highlight_items
