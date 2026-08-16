# Berechnet die beste Route zu den Edelsteinen
from include.zustand import Position, Zustand
from include.permutations import PERMUTATIONS
from include.pathfinding_logics import (
    bfs_distances_from,
    generate_a_star_path,
    get_best_reachable_center,
    follow_a_star_path,
    get_mid,
)
from include.clustering import cluster_frontiers
from include.checks import check_for_change_gems
from include.matrix import (
    reset_matrix_floors,
    make_current_matrix,
    get_current_frontiers,
)
from include.highlighting import debug_print


def move_without_gem(zustand: Zustand):
    import time

    start_time = time.perf_counter_ns()
    cluster_frontiers(zustand)
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
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )

    return move


def check_for_new_path(zustand: Zustand):
    if zustand.opponent is not None:
        get_path_with_opponent(zustand)
    else:
        set_path_to_gem(zustand, zustand.remembered_gems)


def get_route_by_permutations_for_bot(
    position: Position, used_gems, zustand: Zustand
):  # C Mitgabe Botposition und der benutzten Data (normal oder modifiziert)
    import time

    start_time = time.perf_counter_ns()
    gems_count = len(used_gems)  # C zählt gems in der Data
    if gems_count == 0:  # C wenn 0 gems da rückgabe None
        return None
    else:
        if gems_count > 5:
            gems_count = 5
        permutations = PERMUTATIONS[
            gems_count
        ]  # C berechnet alle Reihenfolgen (nur 123 o. 231 o. 321...)

        gem_positions = [g.position for g in used_gems]

        if zustand.with_opponent == True:
            strategic_center = get_best_reachable_center(zustand)
        else:
            strategic_center = get_mid(zustand)
            zustand.mid = strategic_center

        dists_to_center = bfs_distances_from(strategic_center, zustand, gem_positions)

        # 1. Berechne Distanzen vom Bot zu allen Gems
        # Das gibt uns ein Dict: {gem_pos: distanz, ...}
        if position == zustand.bot:
            dist_bot_to_gems = zustand.distances_to_bot
        else:
            dist_bot_to_gems = bfs_distances_from(position, zustand, gem_positions)

        # 2. Berechne Distanzen von jedem Gem zu jedem anderen Gem
        # Das ist wichtig für die Wege zwischen den Steinen
        dist_gem_to_gems = {}
        for g in used_gems:
            # Von diesem Stein zu allen anderen Steinen BFS laufen lassen
            dist_gem_to_gems[g.position] = bfs_distances_from(
                g.position, zustand, gem_positions
            )
        # ---------------------------------------------------------

        best_route = None  # C später für Speicherung der optimalsten Route
        for route in permutations:
            # C Jede Reihenfolge der Edelsteine soll genommen werden
            total_route_distance = 0  # C Variablen zum Speichern der Distanz
            total_route_points = 0
            real_total_route_points = 0

            route_is_valid = True  # Check, ob Weg durch Wände blockiert ist

            for i, gem_index in enumerate(route):
                target_gem = used_gems[gem_index - 1]
                target_pos = target_gem.position

                distance = None

                if i == 0:
                    # Fall 1: Vom Bot zum ersten Stein
                    # Wir schauen in unser vorberechnetes Dict
                    distance = dist_bot_to_gems.get(target_pos)
                else:
                    # Fall 2: Von Stein zu Stein
                    # Vorheriger Stein
                    prev_gem_index = route[i - 1]
                    prev_pos = used_gems[prev_gem_index - 1].position

                    # Hole Distanz aus der Matrix (Von Prev -> Target)
                    if prev_pos in dist_gem_to_gems:
                        distance = dist_gem_to_gems[prev_pos].get(target_pos)

                dist_to_center = dists_to_center[target_pos]
                if dist_to_center == 0:
                    centrality_bonus = 10
                else:
                    centrality_bonus = (1 / dist_to_center) * 5

                # WICHTIG: Wenn distance None ist, ist der Weg durch eine Wand blockiert!
                if distance is None:
                    route_is_valid = False
                    break  # Diese Route abbrechen, sie ist unmöglich

                # Berechnung wie gehabt, aber mit echter Distanz
                total_route_distance += distance
                if (zustand.tick + total_route_distance) > zustand.config.max_ticks:
                    total_route_distance -= distance
                    if i == 0:
                        total_route_points += centrality_bonus
                    break

                # Punkte: Zeit (TTL) - verbrauchte Zeit (Distanz)
                evaluated_points = target_gem.ttl - total_route_distance
                # if zustand.with_opponent == True:
                #     multiplier = 1 - ((total_route_distance * 0.01))
                #    if multiplier < 0:
                #       multiplier = 0.001
                #    debug_print(f"Multiplier {multiplier}", zustand)
                #    evaluated_points = evaluated_points * multiplier
                if evaluated_points <= 0:
                    break
                total_route_points += centrality_bonus
                total_route_points += evaluated_points
                real_total_route_points += evaluated_points

            # Nur wenn die Route valide war (keine Wände im Weg), vergleichen wir sie
            if route_is_valid:
                if best_route is None:
                    best_route = (
                        total_route_points,
                        total_route_distance,
                        route,
                        real_total_route_points,
                    )
                elif total_route_points == best_route[0]:
                    if real_total_route_points > best_route[3]:
                        best_route = (
                            total_route_points,
                            total_route_distance,
                            route,
                            real_total_route_points,
                        )
                elif total_route_points > best_route[0]:
                    best_route = (
                        total_route_points,
                        total_route_distance,
                        route,
                        real_total_route_points,
                    )
        import inspect

        zustand.run_time_analyse.append(
            [
                inspect.currentframe().f_code.co_name,
                (time.perf_counter_ns() - start_time) / 1000000,
            ]
        )

        return best_route  # C effizienteste Route wird zurückgegeben


## Wenn zweiter Bot wird der Pfad so


def get_path_with_opponent(zustand: Zustand):
    route_for_us = get_route_by_permutations_for_bot(
        zustand.bot, zustand.remembered_gems, zustand
    )
    route_for_opponent = get_route_by_permutations_for_bot(
        zustand.opponent, zustand.remembered_gems, zustand
    )

    if (
        route_for_opponent[2][0] == route_for_us[2][0]
    ):  # C route_for...[2] sind die angesteuerten gems, [0] der 1.
        ## Wenn beide den ersten selben gem haben
        gem = route_for_us[2][0]
        gems_position = zustand.remembered_gems[gem - 1].position

        distance_for_us = zustand.distances_to_bot.get(gems_position, 1000)
        dict_opponent = bfs_distances_from(zustand.opponent, zustand, [gems_position])
        distance_for_opponent = dict_opponent.get(gems_position, 1000)

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
                ### Wenn der gegnerische Bot zuerst am nächsten gem ankäme und der eigene bot da auch hin will, aber länger braucht, dann wird nun die Route neuberechnet, so dass der eine Gem nicht mit ein berechnet wird.
                zustand.modified_gems = zustand.remembered_gems.copy()
                del zustand.modified_gems[gem - 1]
                new_route = get_route_by_permutations_for_bot(
                    zustand.bot, zustand.modified_gems, zustand
                )
                if new_route is None:
                    zustand.destination = gems_position
                    return
                else:
                    set_path_to_gem(zustand, zustand.modified_gems)
                    return

        else:
            ### Wenn der gegnerische Bot zuerst am nächsten gem ankäme und der eigene bot da auch hin will, aber länger braucht, dann wird nun die Route neuberechnet, so dass der eine Gem nicht mit ein berechnet wird.
            zustand.modified_gems = zustand.remembered_gems.copy()
            del zustand.modified_gems[gem - 1]
            new_route = get_route_by_permutations_for_bot(
                zustand.bot, zustand.modified_gems, zustand
            )
            if new_route is None:
                zustand.destination = gems_position
                return
            else:
                set_path_to_gem(zustand, zustand.modified_gems)
                return

    else:
        set_path_to_gem(zustand, zustand.remembered_gems)

    return


## setzt den Pfad zum ersten Gem in der Route


def set_path_to_gem(zustand: Zustand, used_gems):
    route_for_us = get_route_by_permutations_for_bot(zustand.bot, used_gems, zustand)

    gem = route_for_us[2][0]
    gems_position = used_gems[gem - 1].position
    zustand.destination = gems_position
