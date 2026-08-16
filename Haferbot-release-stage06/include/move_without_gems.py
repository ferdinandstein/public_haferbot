import math

from include.pathfinding_logics import generate_a_star_path
from include.zustand import Zustand


def initalize_checked_matrix(zustand: Zustand):
    zustand.checked_matrix = [
        [-1 for _ in range(zustand.config.width)] for _ in range(zustand.config.height)
    ]


def actualize_checked_matrix(zustand: Zustand):
    for y in range(zustand.config.height):
        for x in range(zustand.config.width):
            if min(distances_to_all_bots(zustand, (x, y))) < zustand.cutoff_dist:
                zustand.checked_matrix[y][x] = zustand.tick


def distances_to_all_bots(zustand: Zustand, field: tuple):
    """Berechnet die Distanzen von allen Bots zum Feld über Luftlinie"""
    distances = []
    for bot in zustand.teammates:
        if bot is not None:
            distances.append(math.hypot(bot[0] - field[0], bot[1] - field[1]))
    return distances


def move_without_gem(zustand: Zustand):
    """Bewegung ohne Gem"""
    import time

    start_time = time.perf_counter_ns()
    get_last_checked_field(zustand)
    zustand.a_star_path = generate_a_star_path(
        zustand, zustand.destination, zustand.bot
    )
    import inspect

    zustand.run_time_analyse.append(
        [
            inspect.currentframe().f_code.co_name,
            (time.perf_counter_ns() - start_time) / 1000000,
        ]
    )


def get_last_checked_field(zustand: Zustand):
    """Wähle das Feld aus, das am letzten in Signalreichweite war"""
    best_score = -float("inf")
    best_field_to_check = zustand.bot
    for y in range(zustand.config.height):
        for x in range(zustand.config.width):
            if zustand.saved_matrix[y][x] != "X":
                dist = zustand.distances_to_bot[(x, y)]
                age = zustand.tick - zustand.checked_matrix[y][x]

                if age == 0:
                    continue
                score = age - dist * 0.3
                if score > best_score:
                    best_score = score
                    best_field_to_check = (x, y)

    # Wähle das zum Bot nächsten Feld aus, von dem aus das zuvor berechnete Feld in der Signalreichweite ist
    least_dist = float("inf")
    best_field = None
    for x in range(zustand.config.width):
        for y in range(zustand.config.height):
            if zustand.saved_matrix[y][x] != "X":
                dist_bot = zustand.distances_to_bot[(x, y)]
                dist_field = math.hypot(
                    best_field_to_check[0] - x, best_field_to_check[1] - y
                )
                if dist_field < zustand.cutoff_dist - 1 and dist_bot < least_dist:
                    least_dist = dist_field
                    best_field = (x, y)

    zustand.destination = best_field
