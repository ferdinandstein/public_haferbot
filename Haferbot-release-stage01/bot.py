#!/usr/bin/env python3
import sys, json
import heapq
import itertools

sys.stdout.reconfigure(line_buffering=True)
from collections import deque, Counter
import statistics
import time
from pathlib import Path

from permutations import PERMUTATIONS
from zustand import Config, Position, Zustand, Gem, Node
from analyse_und_gewicht_zeug.RandomForestJSON import RandomForestJSON
from analyse_und_gewicht_zeug.weight import SEED, WEIGHT

here = Path(__file__).resolve().parent

STATISTICS_PATH = here / "analyse_und_gewicht_zeug/statistics.json"
RF_MODEL_PATH = here / "analyse_und_gewicht_zeug/best_weight_model.json"
rf_model = RandomForestJSON(RF_MODEL_PATH)


debug_enabled = (
    False  # Wenn das False, dann werden Fehlerüberprüfungsausgaben nicht geprintet
)


def debug_print(message):
    if debug_enabled:
        print(message, file=sys.stderr, flush=True)


def first_tick(data, zustand: Zustand):
    zustand.config = Config(**data["config"])
    vis_bots = data.get("visible_bots", None)

    if vis_bots is None:
        zustand.with_opponent = False
    else:
        zustand.with_opponent = True

    initalize_current_matrix(zustand)  # C macht Tabelle
    initalize_saved_matrix(zustand)
    initalize_real_matrix(zustand)
    initalize_dict_of_tiles(zustand)
    actualize_dict(zustand)
    make_current_matrix(zustand)
    make_saved_matrix(zustand)
    make_real_matrix(zustand)
    get_current_frontiers(zustand)
    get_real_frontiers(zustand)
    cluster_frontiers(zustand)


def initalize_dict_of_tiles(zustand: Zustand):
    width = zustand.config.width
    height = zustand.config.height

    for y in range(height):
        for x in range(width):
            if y == 0 or y == height - 1 or x == 0 or x == width - 1:
                continue
            else:
                zustand.dictionary_of_all_tiles.update(
                    {
                        Position([x, y]): {
                            "tiles": [],
                            "count": 0,
                            "LST": 0.01,
                            "owner": None,
                            "dist": None,
                        }
                    }
                )  # 0.01 statt 0, damit nicht durch 0 geteilt wird


def initalize_current_matrix(
    zustand: Zustand,
):  # C wieder Tabelle in zustand mit höhe weite installiert?
    width = zustand.config.width
    height = zustand.config.height
    zustand.current_matrix = []

    for i in range(
        height
    ):  # C für jedes element der höhe wird eine Zeile in der Tabelle gemacht
        row = []
        for j in range(
            width
        ):  # C und für jedes Element der Breite ein / (bedeutet noch nicht bestimmt)
            if i == 0 or i == height - 1 or j == 0 or j == width - 1:
                row.append("X")  # Rand ist immer Wand
            else:
                row.append("/")  # user input for rows
        zustand.current_matrix.append(row)  # adding rows to the matrix


def initalize_saved_matrix(
    zustand: Zustand,
):  # C wieder Tabelle in zustand mit höhe weite installiert?
    width = zustand.config.width
    height = zustand.config.height
    zustand.saved_matrix = []

    for i in range(
        height
    ):  # C für jedes element der höhe wird eine Zeile in der Tabelle gemacht
        row = []
        for j in range(
            width
        ):  # C und für jedes Element der Breite ein / (bedeutet noch nicht bestimmt)
            if i == 0 or i == height - 1 or j == 0 or j == width - 1:
                row.append("X")  # Rand ist immer Wand
            else:
                row.append("/")  # user input for rows
        zustand.saved_matrix.append(row)  # adding rows to the matrix


def initalize_real_matrix(
    zustand: Zustand,
):  # C wieder Tabelle in zustand mit höhe weite installiert?
    width = zustand.config.width
    height = zustand.config.height
    zustand.real_matrix = []

    for i in range(
        height
    ):  # C für jedes element der höhe wird eine Zeile in der Tabelle gemacht
        row = []
        for j in range(
            width
        ):  # C und für jedes Element der Breite ein / (bedeutet noch nicht bestimmt)
            if i == 0 or i == height - 1 or j == 0 or j == width - 1:
                row.append("X")  # Rand ist immer Wand
            else:
                row.append("/")  # user input for rows
        zustand.real_matrix.append(row)  # adding rows to the matrix


def make_current_matrix(zustand: Zustand):

    for wall in zustand.walls:
        zustand.current_matrix[wall.y][wall.x] = "X"

    for floor in zustand.floors:
        zustand.current_matrix[floor.y][floor.x] = "0"


def make_saved_matrix(zustand: Zustand):
    for wall in zustand.walls:
        zustand.saved_matrix[wall.y][wall.x] = "X"

    for floor in zustand.floors:
        zustand.saved_matrix[floor.y][floor.x] = "0"


def make_real_matrix(zustand: Zustand):
    for wall in zustand.walls:
        zustand.real_matrix[wall.y][wall.x] = "X"


def print_matrix(zustand: Zustand, matrix):
    for i in range(
        zustand.config.height
    ):  #  Das ist dazu da, um die Matrix ordentlich zu printen
        for j in range(zustand.config.width):
            print(matrix[i][j], end=" ", file=sys.stderr, flush=True)
        debug_print(" ")


def reset_matrix_floors(zustand: Zustand):
    y = 0
    for row in zustand.current_matrix:
        x = 0
        for col in row:
            if col == "0" or col == "~":
                zustand.current_matrix[y][x] = "/"
            x += 1
        y += 1


def complete_matrices(zustand: Zustand):
    y = 0
    blocked_count = 0
    free_count = 0
    walls_count = 0
    for row in zustand.saved_matrix:
        x = 0
        for col in row:
            if col == "/":
                zustand.saved_matrix[y][x] = "X"
                zustand.current_matrix[y][x] = "X"
                blocked_count += 1
            elif col == "0":
                if zustand.saved_matrix[y + 1][x] == "X":
                    walls_count += 1
                if zustand.saved_matrix[y - 1][x] == "X":
                    walls_count += 1
                if zustand.saved_matrix[y][x + 1] == "X":
                    walls_count += 1
                if zustand.saved_matrix[y][x - 1] == "X":
                    walls_count += 1
                free_count += 1
            elif col == "X":
                blocked_count += 1
            x += 1
        y += 1
    return walls_count, free_count, blocked_count


def write_statistics(zustand: Zustand, walls, free_count, blocked_count, index):
    avg_view = 0
    median_view = 0
    max_view = 0
    min_view = 100
    views_less_30 = 0
    views_more_150 = 0
    all_walkables = []
    y = 0
    for row in zustand.saved_matrix:
        x = 0
        for col in row:
            if col == "0":

                all_walkables.append(Position([x, y]))
            x += 1
        y += 1

    tile_counts = []

    finished = False
    for walkable in all_walkables[index:]:

        current_time = time.perf_counter_ns()
        if (current_time - zustand.start_time) > 95000000:
            break
        visible, unknown = get_fov(zustand, walkable)
        tiles = list(visible) + list(unknown)
        if len(tiles) > max_view:
            max_view = len(tiles)
        if len(tiles) < min_view:
            min_view = len(tiles)
        if len(tiles) <= 30:
            views_less_30 += 1
        if len(tiles) >= 150:
            views_more_150 += 1

        tile_counts.append(len(tiles))
        index += 1
    if index == len(all_walkables):
        summe = sum(tile_counts)
        laenge = len(tile_counts)
        median_view = statistics.median(tile_counts)
        avg_view = summe / laenge

        def safe_div(a, b):
            return a / b if b != 0 else 0.0

        entry = {
            "seed": SEED,
            "infos": {
                "max_view": max_view,  # Maximale Sicht
                "views_less_30": views_less_30,  # Anzahl Felder mit Sicht < 30
                # ratios
                "max_view_norm": safe_div(avg_view, max_view),
                "walls/blocked": safe_div(walls, blocked_count),
                "min/blocked": safe_div(min_view, blocked_count),
                "walls/width": safe_div(walls, zustand.config.width),
                "max/width": safe_div(max_view, zustand.config.width),
            },
        }

        def write_stats_in_json(entry):
            try:
                with open(STATISTICS_PATH, "r", encoding="utf-8") as f:
                    stats = json.load(f)
                    if not isinstance(stats, list):
                        stats = []
            except (FileNotFoundError, json.JSONDecodeError):
                stats = []

            seed_found = False
            for stat in stats:
                if stat.get("seed") == SEED:
                    seed_found = True
                    # Fehlende Keys ergänzen, vorhandene Werte belassen
                    for key, value in entry["infos"].items():
                        if key not in stat.get("infos", {}):
                            stat["infos"][key] = value
                    break

            if not seed_found:
                # Seed existiert noch nicht
                stats.append(entry)

            with open(STATISTICS_PATH, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2)

        infos = entry["infos"]
        # write_stats_in_json(entry)

        zustand.best_weight = round(rf_model.predict(infos), 4)
        finished = True
        return finished, index
    else:
        finished = False
        return finished, index


def highlight_matrix(matrix):
    highlight_items = []
    if debug_enabled == True:
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

                if item == "~":
                    converted_item = [x, y, "#0066ff6c"]
                    highlight_items.append(converted_item)
                x += 1
            y += 1
    return highlight_items


def highlight_path(zustand: Zustand):
    highlight_items = []
    path_positions = zustand.a_star_path
    if debug_enabled == True and path_positions is not None:
        for position in path_positions:
            converted_item = [position.x, position.y, "#2018fcff"]
            highlight_items.append(converted_item)

    return highlight_items


def highlight_frontiers(zustand: Zustand, frontiers):
    highlight_items = []
    frontier_positions = frontiers
    if debug_enabled == True and frontier_positions is not None:
        for position in frontier_positions:
            converted_item = [position.x, position.y, "#18defcff"]
            highlight_items.append(converted_item)

    return highlight_items


def highlight_clusters(zustand: Zustand):
    highlight_items = []
    clusters_with_mid = zustand.clusters
    if debug_enabled == True and clusters_with_mid is not None:
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
            cluster = cluster_with_mid[0]
            mid = cluster_with_mid[1]
            converted_item = [mid.x, mid.y, colors[(idx + 1) % len(colors)]]
            highlight_items.append(converted_item)
            idx += 1

        # converted_item = [mid.x, mid.y, "#ffffffc1"]
        # highlight_items.append(converted_item)

    return highlight_items


def highlight_fov(visible):
    highlight_items = []

    if debug_enabled == True:

        for tile in visible:
            converted_item = [tile.x, tile.y, "#fc1818ff"]
            highlight_items.append(converted_item)

    return highlight_items


def highlight_dicts_lst(zustand: Zustand):
    highlight_items = []

    if debug_enabled:
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


def write_zustand(data, zustand: Zustand):
    """Setzt den Zustand basierend auf den empfangenen Spieldaten."""
    zustand.tick = data["tick"]
    zustand.bot = Position(data["bot"])
    zustand.initative = data.get("initiative", True)

    if len(data.get("visible_bots", [])) > 0:
        zustand.opponent = Position(data["visible_bots"][0]["position"])
    else:
        zustand.opponent = None

    zustand.walls = [Position(wall) for wall in data["wall"]]

    zustand.floors = [Position(floor) for floor in data["floor"]]

    zustand.visible_gems = [Gem(**gem) for gem in data.get("visible_gems", [])]

    # Wenn der Gegner nicht mehr sichtbar ist, auf None setzen und ignorieren
    if zustand.opponent not in zustand.floors:
        zustand.opponent = None

    for gem in zustand.remembered_gems:
        gem.ttl -= 1

    for gem in zustand.visible_gems:
        if gem not in zustand.remembered_gems:
            zustand.remembered_gems.append(gem)

    for gem in zustand.remembered_gems:
        if zustand.bot == gem.position:
            zustand.remembered_gems.remove(gem)

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


# schauen, ob neu gems dazu gekommen sind oder alte verschwunden


def check_for_change_gems(zustand: Zustand):
    if zustand.remembered_gems == zustand.last_remembered_gems:
        return False
    else:
        return True


def check_if_this_tick_has_gem(zustand: Zustand):
    """Überprüft, ob im aktuellen Tick ein Edelstein sichtbar ist."""
    if len(zustand.remembered_gems) > 0:
        return True
    else:
        return False


def check_if_destination_in_gems(zustand: Zustand):
    for gem in zustand.remembered_gems:
        if gem.position == zustand.destination:
            return True
    return False


# Berechnet die beste Route zu den Edelsteinen


def get_route_by_permutations_for_bot(
    position: Position, used_gems
):  # C Mitgabe Botposition und der benutzten Data (normal oder modifiziert)
    gems_count = len(used_gems)  # C zählt gems in der Data
    if gems_count == 0:  # C wenn 0 gems da rückgabe None
        return None
    else:
        if gems_count > 5:
            gems_count = 5
        permutations = PERMUTATIONS[
            gems_count
        ]  # C berechnet alle Reihenfolgen (nur 123 o. 231 o. 321...)
        best_route = None  # C später für Speicherung der optimalsten Route
        for (
            route
        ) in permutations:  # C Jede Reihenfolge der Edelsteine soll genommen werden
            is_first_gem = True  # C Für Später damit der 1. Edelst. Distanz zum Bot (nicht Stein - Stein)
            total_route_distance = 0  # C Variablen zum Speichern der Distanz
            total_route_points = 0
            for gem_index in route:  # C je gem der Reihenfolge...
                if is_first_gem == True:
                    distance = (
                        position - used_gems[gem_index - 1].position
                    )  # C Distanz Bot-Stein Betrag(xB-xS)+(yB-yS)
                    evaluated_points = (
                        used_gems[gem_index - 1].ttl - distance
                    )  # C gesamt Punkte Stein = Zeit - Distanz
                    is_first_gem = False  # C erster gem wird auf falsch gesetzt
                else:
                    distance = (
                        used_gems[previous_gem_index - 1].position
                        - used_gems[gem_index - 1].position
                    )  # C Distanz Stein-Stein Betrag(xS1-xS2)+(yB1-yS2)
                total_route_distance += (
                    distance  # C Distanz Betrag wird aufaddiert zur Route
                )
                evaluated_points = used_gems[gem_index - 1].ttl - total_route_distance
                previous_gem_index = (
                    gem_index  # C das nun analysierten Gem wird als altes gespeichert
                )
                total_route_points += evaluated_points  # Punkte Für diese Stein Stein Verbindung aufaddiert
            if (
                best_route is None or total_route_points > best_route[0]
            ):  # C wenn die Route besser ist als bisher
                best_route = (
                    total_route_points,
                    total_route_distance,
                    route,
                )  # C speichern als vorläufig beste
        return best_route  # C effizienteste Route wird zurückgegeben


## Wenn zweiter Bot wird der Pfad so


def get_path_with_opponent(zustand: Zustand):
    route_for_us = get_route_by_permutations_for_bot(
        zustand.bot, zustand.remembered_gems
    )
    route_for_opponent = get_route_by_permutations_for_bot(
        zustand.opponent, zustand.remembered_gems
    )

    if (
        route_for_opponent[2][0] == route_for_us[2][0]
    ):  # C route_for...[2] sind die angesteuerten gems, [0] der 1.
        ## Wenn beide den ersten selben gem haben
        gem = route_for_us[2][0]
        gems_position = zustand.remembered_gems[gem - 1].position

        distance_for_us = len(generate_a_star_path(zustand, gems_position, zustand.bot))
        distance_for_opponent = len(
            generate_a_star_path(zustand, gems_position, zustand.opponent)
        )

        if distance_for_us < distance_for_opponent:
            zustand.destination = gems_position
            return
        elif distance_for_us == distance_for_opponent:
            if distance_for_us % 2 == 0:
                last_initative = not zustand.initative
            else:
                last_initative = zustand.initative
            if last_initative == True:
                zustand.destination = gems_position
            else:
                zustand.destination = zustand.clusters[0][1]

        else:
            ### Wenn der gegnerische Bot zuerst am nächsten gem ankäme und der eigene bot da auch hin will, aber länger braucht, dann wird nun die Route neuberechnet, so dass der eine Gem nicht mit ein berechnet wird.
            zustand.modified_gems = zustand.remembered_gems.copy()
            del zustand.modified_gems[gem - 1]
            new_route = get_route_by_permutations_for_bot(
                zustand.bot, zustand.modified_gems
            )
            if new_route is None:
                zustand.destination = zustand.clusters[0][1]
                return
            else:
                set_path_to_gem(zustand, zustand.modified_gems)
                return

    else:
        set_path_to_gem(zustand, zustand.remembered_gems)

    return


# Funktion um zu überprüfen, ob ein neuer Pfad berechnet werden muss


def check_for_new_path(zustand: Zustand):
    if zustand.opponent is not None:
        get_path_with_opponent(zustand)
    else:
        set_path_to_gem(zustand, zustand.remembered_gems)


## setzt den Pfad zum ersten Gem in der Route


def set_path_to_gem(zustand: Zustand, used_gems):
    route_for_us = get_route_by_permutations_for_bot(zustand.bot, used_gems)

    gem = route_for_us[2][0]
    gems_position = used_gems[gem - 1].position
    zustand.destination = gems_position


# Funktion um dem Pfad zu folgen


def generate_a_star_path(zustand: Zustand, destination, origin):

    # Generiert einen Pfad vom aktuellen Bot-Standort zum Ziel (destination) mit dem A*-Algorithmus.
    # Der Algorithmus arbeitet mit einer Prioritätswarteschlange (Heap), um immer den vielversprechendsten Knoten zu wählen.
    # Die Kosten werden als f = g + h berechnet, wobei:
    #    g = bisherige Kosten vom Start
    #    h = Heuristik (geschätzte Entfernung zum Ziel)
    # Die Funktion gibt eine Liste von Positionen zurück, die den Pfad vom Start zum Ziel darstellen.

    # Startknoten initialisieren
    start_node = Node()
    start_node.position = origin  # Startposition ist die aktuelle Bot-Position
    goal_node = destination  # Zielposition
    # Ein heapq Element hat alle Elemente innerhalb sortiert. Oben steht also immer das mit den niedrigsten f-Kosten
    # Priority queue (min-heap) für offene Knoten: (f_cost, counter, node)
    counter = itertools.count()  # Zähler für eindeutige Heap-Einträge
    open_heap = []  # Heap für offene Knoten
    open_dict = {}  # Dictionary: (x,y) -> bester Node im Open-Set
    closed_set = set()  # Menge der bereits besuchten Positionen

    # Kosten für den Startknoten setzen
    start_node.g_cost = 0  # Start hat keine Kosten
    # h_cost ist die Heuristik: Differenz zur Zielposition (siehe __sub__ in Position)
    start_node.h_cost = start_node.position - goal_node
    start_node.f_cost = start_node.g_cost + start_node.h_cost
    start_node.parent = None  # Start hat keinen Vorgänger

    start_pos = (start_node.position.x, start_node.position.y)
    open_dict[start_pos] = start_node
    heapq.heappush(
        open_heap, (start_node.f_cost, next(counter), start_node)
    )  # Fügt was hinzu

    # Hauptschleife: Solange noch offene Knoten existieren
    while open_heap:
        # Hole den Knoten mit den niedrigsten f-Kosten

        f_cost, _, first_node = heapq.heappop(
            open_heap
        )  # gibt das kleinste erste Element zurück
        current_nodes = [first_node]
        # alle weiteren mit gleichem f_cost holen
        while open_heap and open_heap[0][0] == f_cost:
            _, _, node = heapq.heappop(open_heap)
            current_nodes.append(node)
        best_wert = 10000
        # Node als current wählen, die am nächsten auf Achse ist.
        for node in current_nodes:
            dist_x = abs(node.position.x - destination.x)
            dist_y = abs(node.position.y - destination.y)
            least = min(dist_x, dist_y)
            if least < best_wert:
                current_node = node
                best_wert = least

        current_nodes.remove(current_node)

        for node in current_nodes:
            heapq.heappush(open_heap, (node.f_cost, next(counter), node))

        cur_pos = (current_node.position.x, current_node.position.y)

        # Überspringe veraltete Heap-Einträge
        if cur_pos in closed_set:
            continue

        # Ziel erreicht?
        if (
            current_node.position.x == goal_node.x
            and current_node.position.y == goal_node.y
        ):
            # Rekonstruiere und gib den Pfad zurück
            return reconstruct_path(current_node)

        # Markiere aktuelle Position als besucht
        closed_set.add(cur_pos)

        # Ermittle alle gültigen Nachbarn
        neighbours = get_neighbours_of_node(current_node, zustand)

        for neighbour in neighbours:
            npos = (neighbour.position.x, neighbour.position.y)
            if npos in closed_set:
                continue

            # Berechne die Kosten zum Nachbarn
            temporally_g_cost = (
                current_node.g_cost + 1
            )  # Annahme: jeder Schritt kostet 1

            existing = open_dict.get(npos)
            # Falls der Nachbar noch nicht im Open-Set ist oder ein besserer Pfad gefunden wurde
            if existing is None or temporally_g_cost < existing.g_cost:
                # Setze den Vorgänger (für Pfadrekonstruktion)
                neighbour.parent = current_node
                neighbour.g_cost = temporally_g_cost
                neighbour.h_cost = neighbour.position - goal_node
                neighbour.f_cost = neighbour.g_cost + neighbour.h_cost
                open_dict[npos] = neighbour
                heapq.heappush(open_heap, (neighbour.f_cost, next(counter), neighbour))
    # Kein Pfad gefunden
    return None


def get_neighbours_of_node(current_node: Node, zustand: Zustand):

    # Gibt alle benachbarten freien Felder (Nodes) von einem Feld zurück.
    # Ein Feld ist frei, wenn in der Matrix an dieser Stelle "0" steht.
    # Es werden nur Felder innerhalb der Spielfeldgrenzen betrachtet.
    # Rückgabe: Liste von Node-Objekten für Norden, Süden, Osten, Westen (keine Diagonalen).

    neighbours = []

    x = current_node.position.x
    y = current_node.position.y
    width = zustand.config.width
    height = zustand.config.height

    # Norden
    if y - 1 >= 0 and zustand.saved_matrix[y - 1][x] == "0":
        neighbour = Node()
        neighbour.position = Position([x, y - 1])
        neighbours.append(neighbour)

    # Süden
    if y + 1 < height and zustand.saved_matrix[y + 1][x] == "0":
        neighbour = Node()
        neighbour.position = Position([x, y + 1])
        neighbours.append(neighbour)

    # Osten
    if x + 1 < width and zustand.saved_matrix[y][x + 1] == "0":
        neighbour = Node()
        neighbour.position = Position([x + 1, y])
        neighbours.append(neighbour)

    # Westen
    if x - 1 >= 0 and zustand.saved_matrix[y][x - 1] == "0":
        neighbour = Node()
        neighbour.position = Position([x - 1, y])
        neighbours.append(neighbour)

    return neighbours


def reconstruct_path(current_node):
    """
    Rekonstruiert den Pfad vom Ziel zum Start, indem die parent-Referenzen verfolgt werden.
    Gibt eine Liste von Positionen (vom Start bis zum Ziel) zurück.
    """
    path_positions = []
    node = current_node
    seen = set()  # Schutz vor Endlosschleifen
    while node is not None:
        pos = node.position
        key = (pos.x, pos.y)
        if key in seen:  # wenn wir schon mal bei der Position waren stimmt was nicht
            break
        seen.add(key)
        path_positions.append(pos)
        node = node.parent

    path_positions.reverse()  # Start -> Ziel
    return path_positions


def bfs_distances_from(origin: Position, zustand: Zustand, targets):
    """
    BFS from origin to a list of target Positions. Returns a dict mapping (x,y) -> distance (int) or None if unreachable.
    Stops early once all targets are found.
    """

    width = zustand.config.width
    height = zustand.config.height
    saved = zustand.saved_matrix

    start = origin
    queue = deque([start])
    distances = {start: 0}

    targets_set = set(targets)
    found = {}

    if start in targets_set:
        found[start] = 0
    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    # BFS main loop
    while queue:
        current = queue.popleft()
        x, y = current.x, current.y
        distance = distances[current]

        if len(found) == len(targets_set):
            break

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if saved[ny][nx] == "X":
                continue
            key = Position([nx, ny])
            if key in distances:
                continue
            neighbour_dist = distance + 1
            distances[key] = neighbour_dist
            if key in targets_set:
                found[key] = neighbour_dist
            queue.append(key)

    # Build result mapping only for requested targets
    result = {}
    for t in targets_set:
        result[t] = found.get(t)
    return result


def follow_a_star_path(zustand: Zustand):
    position = zustand.a_star_path[0]

    if zustand.bot.x == position.x and zustand.bot.y == position.y:
        # remove the reached node
        zustand.a_star_path.remove(position)
        # if path is now empty, nothing to do
        if len(zustand.a_star_path) == 0:
            return "WAIT"
        # otherwise continue towards the next position
        position = zustand.a_star_path[0]

    # other bot in the way
    if zustand.opponent is not None:
        if position == zustand.opponent:
            # look, if other direction is possible and useful
            # for path useful tiles, check if bot can go there
            destination = zustand.destination
            if destination.x > zustand.bot.x:
                if (
                    zustand.saved_matrix[zustand.bot.y][zustand.bot.x + 1] == "0"
                    and zustand.opponent.x != zustand.bot.x + 1
                ):
                    zustand.a_star_path.insert(0, zustand.bot)
                    return "E"
            elif destination.x < zustand.bot.x:
                if (
                    zustand.saved_matrix[zustand.bot.y][zustand.bot.x - 1] == "0"
                    and zustand.opponent.x != zustand.bot.x - 1
                ):
                    zustand.a_star_path.insert(0, zustand.bot)
                    return "W"
            elif destination.y > zustand.bot.y:
                if (
                    zustand.saved_matrix[zustand.bot.y + 1][zustand.bot.x] == "0"
                    and zustand.opponent.y != zustand.bot.y + 1
                ):
                    zustand.a_star_path.insert(0, zustand.bot)
                    return "S"
            elif destination.y < zustand.bot.y:
                if (
                    zustand.saved_matrix[zustand.bot.y - 1][zustand.bot.x] == "0"
                    and zustand.opponent.y != zustand.bot.y - 1
                ):
                    zustand.a_star_path.insert(0, zustand.bot)
                    return "N"
            # No alternative found, that is in the way of destination

            fov_bot, bot_unknown = get_fov(zustand, zustand.bot)
            bot_all = fov_bot | bot_unknown
            fov_opponent, opponent_unknown = get_fov(zustand, zustand.opponent)
            opponent_all = fov_opponent | opponent_unknown
            if len(bot_all) > len(opponent_all):
                return "WAIT"
            # try to step aside, because opponent has larger FOV
            dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
            move_dict = {
                "E": (1, 0),
                "W": (-1, 0),
                "S": (0, 1),
                "N": (0, -1),
                "WAIT": (0, 0),
            }
            for dx, dy in dirs:
                nx = zustand.bot.x + dx
                ny = zustand.bot.y + dy
                if (
                    0 <= nx < zustand.config.width
                    and 0 <= ny < zustand.config.height
                    and zustand.saved_matrix[ny][nx] == "0"
                    and Position([nx, ny]) != zustand.opponent
                    and move_dict[zustand.last_move] != (-dx, -dy)
                ):
                    # found alternative position to step aside
                    if dx == 1:
                        zustand.a_star_path.insert(
                            0, zustand.bot
                        )  # reinsert current position
                        return "E"
                    elif dx == -1:
                        zustand.a_star_path.insert(0, zustand.bot)
                        return "W"
                    elif dy == 1:
                        zustand.a_star_path.insert(0, zustand.bot)
                        return "S"
                    elif dy == -1:
                        zustand.a_star_path.insert(0, zustand.bot)
                        return "N"
            else:
                # Going back is last option, check if possible
                dx, dy = move_dict[zustand.last_move]
                nx = zustand.bot.x + dx
                ny = zustand.bot.y + dy
                if (
                    0 <= nx < zustand.config.width
                    and 0 <= ny < zustand.config.height
                    and zustand.saved_matrix[ny][nx] == "0"
                    and Position([nx, ny]) != zustand.opponent
                ):
                    # continue last move if possible
                    zustand.a_star_path.insert(0, zustand.bot)
                    return zustand.last_move
            return "WAIT"

    # Move towards the next position
    if zustand.bot.x < position.x:
        return "E"
    elif zustand.bot.x > position.x:
        return "W"
    elif zustand.bot.y < position.y:
        return "S"
    elif zustand.bot.y > position.y:
        return "N"


def get_current_frontiers(zustand: Zustand):
    zustand.frontiers = []
    y = 0
    for row in zustand.current_matrix:
        x = 0
        for col in row:
            if col == "0":
                if (
                    zustand.current_matrix[y - 1][x] == "/"
                    or zustand.current_matrix[y + 1][x] == "/"
                    or zustand.current_matrix[y][x - 1] == "/"
                    or zustand.current_matrix[y][x + 1] == "/"
                ):
                    zustand.frontiers.append(Position([x, y]))
            x += 1
        y += 1


def get_old_frontiers(zustand: Zustand):
    frontiers = []
    y = 0
    for row in zustand.current_matrix:
        x = 0
        for col in row:

            if col == "0":
                if (
                    zustand.current_matrix[y - 1][x] == "/"
                    or zustand.current_matrix[y + 1][x] == "/"
                    or zustand.current_matrix[y][x - 1] == "/"
                    or zustand.current_matrix[y][x + 1] == "/"
                ):
                    frontiers.append(Position([x, y]))

                if (
                    zustand.current_matrix[y - 1][x] == "~"
                    or zustand.current_matrix[y + 1][x] == "~"
                    or zustand.current_matrix[y][x - 1] == "~"
                    or zustand.current_matrix[y][x + 1] == "~"
                ):
                    frontiers.append(Position([x, y]))
            x += 1
        y += 1

    return frontiers


def get_real_frontiers(zustand: Zustand):
    zustand.real_frontiers = []
    used_matrix = []
    used_matrix = [row.copy() for row in zustand.real_matrix]

    for floor in zustand.floors:
        used_matrix[floor.y][floor.x] = "0"
    y = 0
    for row in used_matrix:
        x = 0
        for col in row:
            if col == "0":
                if (
                    used_matrix[y - 1][x] == "/"
                    or used_matrix[y + 1][x] == "/"
                    or used_matrix[y][x - 1] == "/"
                    or used_matrix[y][x + 1] == "/"
                ):
                    zustand.real_frontiers.append(Position([x, y]))

            x += 1
        y += 1


def get_saved_frontiers(zustand: Zustand):
    frontiers = []
    y = 0
    for row in zustand.saved_matrix:
        x = 0
        for col in row:
            if col == "0":
                if (
                    zustand.saved_matrix[y - 1][x] == "/"
                    or zustand.saved_matrix[y + 1][x] == "/"
                    or zustand.saved_matrix[y][x - 1] == "/"
                    or zustand.saved_matrix[y][x + 1] == "/"
                ):
                    frontiers.append(Position([x, y]))

            x += 1
        y += 1
    zustand.saved_frontiers = frontiers


def cluster_frontiers(zustand: Zustand):
    clusters = []
    visited = set()

    # Alle möglichen Richtungen
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (-1, -1), (1, -1)]

    # Frontier als set
    frontier_set = set(zustand.frontiers)

    for start in zustand.frontiers:
        if start in visited:
            continue

        # Neues Cluster beginnen
        queue = deque([start])
        cluster = []
        visited.add(start)

        while queue:
            current = queue.popleft()  # ersten wert entfernen
            cluster.append(current)

            # Nachbarn durchsuchen
            for dr, dc in dirs:
                nr, nc = current.x + dr, current.y + dc
                neighbour_pos = Position([nr, nc])
                if neighbour_pos in frontier_set and neighbour_pos not in visited:
                    visited.add(neighbour_pos)
                    queue.append(neighbour_pos)

        clusters.append(cluster)

    clusters_with_mid = get_mid_for_each_cluster(zustand, clusters)
    zustand.clusters = clusters_with_mid
    assign_unknowns_to_frontiers(zustand)

    # Einmalig: Anzahl Tiles je Owner (cluster id) berechnen
    cluster_tile_counts = {}
    cluster_sum_ages = {}
    cluster_sum_dist = {}
    cluster_score = {}
    for info in zustand.dictionary_of_all_tiles.values():
        owner = info.get("owner")
        if owner is None:
            continue
        dist = info.get("dist", 0.01)
        age = zustand.tick - info.get("LST", zustand.tick)

        if age < 3:
            continue

        cluster_sum_dist[owner] = cluster_sum_dist.get(owner, 0) + dist

        cluster_sum_ages[owner] = cluster_sum_ages.get(owner, 0) + age

        cluster_tile_counts[owner] = cluster_tile_counts.get(owner, 0) + 1

        cluster_score[owner] = cluster_score.get(owner, 0) + (
            age / (dist * 0.21875) if dist > 0 else 0
        )

    # Map cluster object -> index, damit wir nicht .index() auf der Liste aufrufen müssen
    cluster_index_map = {id(cwm): idx for idx, cwm in enumerate(clusters_with_mid)}

    def sort_by_path_length_and_points(cluster_with_mid_of_cluster):
        # Cluster-ID per Map (schnell)
        idx = cluster_index_map.get(id(cluster_with_mid_of_cluster))
        tiles_of_cluster = cluster_tile_counts.get(idx, 0)
        sum_ages_of_cluster = cluster_sum_ages.get(idx, 0)
        cluster_score_here = cluster_score.get(idx, 0)
        cluster_sum_distances = cluster_sum_dist.get(idx, 0)

        if zustand.with_opponent == True:
            tile_weight = 1
            dist_weight = 3.875
            age_weight = 0.6875
            cluster_and_total_weight = 2.09375
            w1 = -0.0625
            w2 = 4.25
            w3 = 4.0625
            w4 = 3.875
            w5 = 1.0625
        else:
            tile_weight = 1
            dist_weight = 0.96875
            age_weight = 0
            cluster_and_total_weight = 2
            w1 = -0.0625
            w2 = 2.75
            w3 = 0.3125
            w4 = 4.15625
            w5 = 2.0

        cluster_tiles_points = (
            tiles_of_cluster
            / (
                (
                    cluster_sum_distances / tiles_of_cluster
                    if tiles_of_cluster > 0
                    else 1000
                )
                * dist_weight
            )
            + (sum_ages_of_cluster / tiles_of_cluster if tiles_of_cluster > 0 else 1000)
            * age_weight
        )

        mid = cluster_with_mid_of_cluster[1]
        _, visible_unknown = get_fov(zustand, mid)

        distance = zustand.dictionary_of_all_tiles[mid]["dist"]

        unknown_tiles = len(visible_unknown)
        sum_age = 0

        for tile in visible_unknown:
            sum_age += zustand.tick - zustand.dictionary_of_all_tiles[tile]["LST"]
        avg_age = sum_age / len(visible_unknown) if len(visible_unknown) > 0 else 0

        max_gems = zustand.config.max_gems
        spawn_rate_multiplier = 1 + ((zustand.config.gem_spawn_rate - 0.05) * 30)

        if max_gems == 1:
            total_points = (
                avg_age * (w1 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * 1
            )
        elif max_gems == 2:
            total_points = (
                avg_age * (w2 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * 1
            )
        elif max_gems == 3:
            total_points = (
                avg_age * (w3 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * 1
            )
        elif max_gems == 4:
            total_points = (
                avg_age * (w4 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * 1
            )
        elif max_gems == 5:
            total_points = (
                avg_age * (w5 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * 1
            )
        else:
            total_points = (
                avg_age * (w5 * spawn_rate_multiplier)
                + unknown_tiles * tile_weight
                - distance * 1
            )
        return cluster_tiles_points * cluster_and_total_weight + total_points

    clusters_with_mid.sort(key=sort_by_path_length_and_points, reverse=True)
    # Die Cluster weden anhand ihres Besten Fronier Feldes sortiert, nach sichtbaren unbekannten Feldern und Distanz und noch mehr. Am Anfang von sorierter Liste bester Cluster
    zustand.clusters = clusters_with_mid


def get_mid_for_each_cluster(zustand: Zustand, clusters):
    """'Für jedes Cluster wird der Frontier mit der Sicht auf möglichst viele unbekannte (/) Felder ausgewählt."""
    clusters_with_mid = []
    for cluster in clusters:
        best_view = 0
        best_frontier = cluster[0]
        for frontier in cluster:
            _, view = get_fov(zustand, frontier)
            if len(view) > best_view:
                best_view = len(view)
                best_frontier = frontier

        clusters_with_mid.append((cluster, best_frontier))
    return clusters_with_mid


def get_fov(zustand: Zustand, origin: Position):
    """Gibt zurück visible walkable und unknown tiles vom origin aus gesehen."""

    if zustand.dictionary_of_all_tiles[origin]["tiles"] != []:
        tiles = zustand.dictionary_of_all_tiles[origin]["tiles"]
        matrix = zustand.current_matrix

        visible_walkable = set()
        visible_unknown = set()

        for pos in tiles:
            cell = matrix[pos.y][pos.x]
            if cell == "0":
                visible_walkable.add(pos)
            elif cell == "/":
                visible_unknown.add(pos)

        return visible_walkable, visible_unknown
    saved = zustand.saved_matrix
    current = zustand.current_matrix
    rows = len(saved)
    cols = len(saved[0])

    visible_walkable = set()
    visible_unknown = set()

    def is_visible_till(p_x, p_y):
        """Prüfe Sichtlinie zwischen origin und p_x, p_y mit Bresenham-Linie.

        Verbesserungen:
        - Endpunkte werden innerhalb des gültigen Bereichs verwendet.
        - Eine Kachel blockiert die Sicht, wenn entweder `saved` oder `current` ein "X" hat.
        """
        # Check ob innerhalb der Grenzen
        p_x = max(0, min(cols - 1, p_x))
        p_y = max(0, min(rows - 1, p_y))

        dx = abs(p_x - origin.x)
        dy = abs(p_y - origin.y)

        x, y = origin.x, origin.y

        n = dx + dy
        x_inc = 1 if p_x > origin.x else -1
        y_inc = 1 if p_y > origin.y else -1
        error = dx - dy
        dx2 = dx * 2
        dy2 = dy * 2

        for _ in range(n + 1):
            # Stop, wenn außerhalb (sollte nicht passieren)
            if not (0 <= y < rows and 0 <= x < cols):
                break
            # Sicht wird durch bekannte Wände in entweder saved oder current geblockt
            if saved[y][x] == "X" or current[y][x] == "X":
                return
            if current[y][x] == "0":
                visible_walkable.add((x, y))
            elif current[y][x] == "/":
                visible_unknown.add((x, y))
            if x == p_x and y == p_y:
                return
            if error > 0:
                x += x_inc
                error -= dy2
            else:
                y += y_inc
                error += dx2
        return

    # Für jedes Randteil wird die Linie gezogen (Endpoints clamped innerhalb von is_visible_till)
    for y in range(rows):
        is_visible_till(0, y)
        is_visible_till(cols, y)
    for x in range(cols):
        is_visible_till(x, 0)
        is_visible_till(x, rows)

    # Konvertiere Tupelmengen in Position-Objekte
    visible_walkable_positions = {Position([x, y]) for x, y in visible_walkable}
    visible_unknown_positions = {Position([x, y]) for x, y in visible_unknown}
    if zustand.saved_frontiers == []:
        all_tiles = visible_unknown_positions | visible_walkable_positions
        zustand.dictionary_of_all_tiles[origin].update(
            {
                "tiles": all_tiles,
                "count": len(all_tiles),
                "LST": zustand.dictionary_of_all_tiles[origin]["LST"],
                "owner": None,
                "dist": None,
            }
        )
    return visible_walkable_positions, visible_unknown_positions


def actualize_dict(zustand: Zustand):
    for tile in zustand.floors:
        zustand.dictionary_of_all_tiles[tile].update(
            {
                "tiles": zustand.dictionary_of_all_tiles[tile]["tiles"],
                "count": len(zustand.dictionary_of_all_tiles[tile]["tiles"]),
                "LST": zustand.tick,
                "owner": None,
                "dist": None,
            }
        )  # LST = last seen tick

    if zustand.opponent is not None:
        walkable, unknown = get_fov(zustand, zustand.opponent)
        opponent_fov = list(walkable) + list(unknown)
        for tile in opponent_fov:
            zustand.dictionary_of_all_tiles[tile].update(
                {
                    "tiles": zustand.dictionary_of_all_tiles[tile]["tiles"],
                    "count": len(zustand.dictionary_of_all_tiles[tile]["tiles"]),
                    "LST": zustand.tick,
                    "owner": None,
                    "dist": None,
                }
            )  # LST = last seen tick

    if zustand.bot in zustand.dictionary_of_all_tiles:
        return
    # Sichtfeld des Bots speichern
    tiles = {zustand.floors}
    count = len(tiles)
    zustand.dictionary_of_all_tiles[zustand.bot].update(
        {
            "tiles": tiles,
            "count": count,
            "LST": zustand.tick,
            "owner": None,
            "dist": None,
        }
    )


def assign_unknowns_to_frontiers(zustand: Zustand):
    local_start = time.perf_counter_ns()

    width = zustand.config.width
    height = zustand.config.height

    queue = deque()
    for tile in zustand.dictionary_of_all_tiles.values():
        tile["owner"] = None
        tile["dist"] = None

    # compute distances from bot to all cluster mids in one BFS run
    mids = [cluster[1] for cluster in zustand.clusters]
    # Hier wird eine BFS ausgeführt, die die Distanzen vom Bot zu allen Mittelpunkten der Cluster berechnet.
    # Denn A* wäre hier zu langsam, da es viele Cluster geben kann.
    mid_distances = bfs_distances_from(zustand.bot, zustand, mids)
    # present a mapping Position -> distance for debugging

    for frontier_id, cluster in enumerate(zustand.clusters):
        mid = cluster[1]
        dist_mid = mid_distances[mid]
        zustand.dictionary_of_all_tiles[mid]["owner"] = frontier_id
        zustand.dictionary_of_all_tiles[mid]["dist"] = dist_mid
        queue.append(mid)
        for frontier in cluster[0]:
            zustand.dictionary_of_all_tiles[frontier]["owner"] = frontier_id
            zustand.dictionary_of_all_tiles[frontier]["dist"] = dist_mid
            queue.append(frontier)

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    # BFS um unbekannte Felder den Frontiers zuzuordnen
    i = 0

    while queue:

        # Abbrechen bei Zeitüberschreitung von 5.0 ms
        if time.perf_counter_ns() - local_start > 5.0 * 1000000:
            debug_print("Timeout during assignment of unknowns to frontiers.")
            debug_print(f"Processed {i} tiles so far.")
            debug_print(f"Took {(time.perf_counter_ns() - local_start) / 1000000} ms")
            break

        field = queue.popleft()

        for dx, dy in directions:
            nx, ny = field.x + dx, field.y + dy
            pos_neighbour = Position([nx, ny])

            if not (0 <= nx < width and 0 <= ny < height):
                continue

            if zustand.current_matrix[ny][nx] == "0":  # Boden
                continue
            if zustand.current_matrix[ny][nx] == "X":  # Wand
                continue

            if zustand.dictionary_of_all_tiles[pos_neighbour]["owner"] is None:
                zustand.dictionary_of_all_tiles[pos_neighbour]["owner"] = (
                    zustand.dictionary_of_all_tiles[field]["owner"]
                )
                zustand.dictionary_of_all_tiles[pos_neighbour]["dist"] = (
                    zustand.dictionary_of_all_tiles[field]["dist"] + 1
                )
                queue.append(pos_neighbour)

        i += 1


def main():
    """main game loop"""

    zustand = Zustand()
    is_first_tick = True
    matrices_finished = False
    zustand.remembered_gems = []

    for line in sys.stdin:
        zustand.start_time = time.perf_counter_ns()
        data = json.loads(line)
        write_zustand(data, zustand)

        if is_first_tick == True:
            first_tick(data, zustand)
            is_first_tick = False
            zustand.destination = zustand.clusters[0][1]
            zustand.a_star_path = generate_a_star_path(
                zustand, zustand.destination, zustand.bot
            )
            move = follow_a_star_path(zustand)

        else:
            actualize_dict(zustand)
            make_saved_matrix(zustand)
            make_current_matrix(zustand)
            make_real_matrix(zustand)

            get_current_frontiers(zustand)
            if zustand.frontiers == []:
                reset_matrix_floors(zustand)
                make_current_matrix(zustand)
                get_current_frontiers(zustand)
            get_saved_frontiers(zustand)
            get_real_frontiers(zustand)

            cluster_frontiers(zustand)

            if zustand.saved_frontiers == []:
                if matrices_finished == False:
                    complete_matrices(zustand)
                    matrices_finished = True

            if (
                check_for_change_gems(zustand) == True
                and check_if_this_tick_has_gem(zustand) == True
            ):
                check_for_new_path(zustand)
                zustand.a_star_path = generate_a_star_path(
                    zustand, zustand.destination, zustand.bot
                )
                move = follow_a_star_path(zustand)
            # sonst wenn keine gems da sind
            elif check_if_this_tick_has_gem(zustand) == False:
                if check_for_change_gems(zustand) == True:
                    reset_matrix_floors(zustand)
                    make_current_matrix(zustand)
                    get_current_frontiers(zustand)
                    cluster_frontiers(zustand)
                    zustand.destination = zustand.clusters[0][1]
                    zustand.a_star_path = generate_a_star_path(
                        zustand, zustand.destination, zustand.bot
                    )
                    move = follow_a_star_path(zustand)
                else:

                    if zustand.frontiers != []:
                        if zustand.a_star_path is None or zustand.a_star_path == []:

                            zustand.destination = zustand.clusters[0][1]
                            zustand.a_star_path = generate_a_star_path(
                                zustand, zustand.destination, zustand.bot
                            )
                            move = follow_a_star_path(zustand)
                        else:
                            if zustand.clusters[0][1] == zustand.last_clusters[0][1]:
                                move = follow_a_star_path(zustand)
                            else:
                                zustand.destination = zustand.clusters[0][1]
                                zustand.a_star_path = generate_a_star_path(
                                    zustand, zustand.destination, zustand.bot
                                )
                                move = follow_a_star_path(zustand)
                    elif zustand.frontiers == []:
                        reset_matrix_floors(zustand)
                        make_current_matrix(zustand)
                        get_current_frontiers(zustand)
                        # Fallback, wenn nach dem Reset immer noch keine Frontier sind. Passiert manchmal

                        cluster_frontiers(zustand)
                        zustand.destination = zustand.clusters[0][1]

                        zustand.a_star_path = generate_a_star_path(
                            zustand, zustand.destination, zustand.bot
                        )
                        move = follow_a_star_path(zustand)
            elif (
                check_if_this_tick_has_gem(zustand) == True
                and check_for_change_gems(zustand) == False
            ):
                if check_if_destination_in_gems(zustand) == True:
                    move = follow_a_star_path(zustand)
                else:
                    check_for_new_path(zustand)
                    zustand.a_star_path = generate_a_star_path(
                        zustand, zustand.destination, zustand.bot
                    )
                    move = follow_a_star_path(zustand)
            else:
                move = "WAIT"

        highlight_items = highlight_matrix(
            zustand.current_matrix
        ) + highlight_frontiers(zustand, zustand.frontiers)
        highlight_message = {"highlight": highlight_items}

        zustand.last_remembered_gems = zustand.remembered_gems.copy()
        zustand.last_move = move
        zustand.last_clusters = zustand.clusters.copy()

        print(
            move,
            json.dumps(highlight_message),
            flush=True,
        )


if __name__ == "__main__":
    main()
