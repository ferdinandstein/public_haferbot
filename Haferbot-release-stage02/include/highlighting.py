from include.zustand import Position, Zustand
import sys


def debug_print(message, zustand: Zustand):
    if zustand.debug_enabled:
        print(message, file=sys.stderr, flush=True)


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
            converted_item = [position.x, position.y, "#2018fcff"]
            highlight_items.append(converted_item)

    return highlight_items


def highlight_gems(gems, zustand: Zustand):
    highlight_items = []
    if zustand.debug_enabled == True and len(gems) != 0:
        for gem in gems:
            converted_item = [gem.position.x, gem.position.y, "#e918fcff"]
            highlight_items.append(converted_item)

    return highlight_items


def highlight_frontiers(frontiers, zustand: Zustand):
    highlight_items = []
    frontier_positions = frontiers
    if zustand.debug_enabled == True and frontier_positions is not None:
        for position in frontier_positions:
            converted_item = [position.x, position.y, "#18defcff"]
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
        #        converted_item = [position.x, position.y, color]
        #        highlight_items.append(converted_item)

        for y in range(zustand.config.height):
            for x in range(zustand.config.width):
                if zustand.current_matrix[y][x] == "/":
                    if (
                        zustand.dictionary_of_all_tiles[Position([x, y])]["owner"]
                        is not None
                    ):
                        color = colors[
                            zustand.dictionary_of_all_tiles[Position([x, y])]["owner"]
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
            converted_item = [mid.x, mid.y, colors[(idx + 1) % len(colors)]]
            highlight_items.append(converted_item)
            idx += 1

        # converted_item = [mid.x, mid.y, "#ffffffc1"]
        # highlight_items.append(converted_item)

    return highlight_items


def highlight_fov(visible, zustand: Zustand):
    if len(visible) == 0:
        return []
    highlight_items = []

    if zustand.debug_enabled == True and visible is not None:

        for tile in visible:
            try:
                converted_item = [tile.x, tile.y, "#fc1818ff"]
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
            converted_item = [position.x, position.y, f"#{colour:06X}"]
            highlight_items.append(converted_item)

    return highlight_items
