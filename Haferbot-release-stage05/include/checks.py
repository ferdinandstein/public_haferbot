from include.zustand import Zustand


def check_for_change_gems(zustand: Zustand):
    if (
        zustand.remembered_gems == zustand.last_remembered_gems
        and zustand.hypothetical_gems == zustand.last_hypothetical_gems
    ):
        return False
    else:
        return True


def check_if_this_tick_has_gem(zustand: Zustand):
    """Überprüft, ob im aktuellen Tick ein Edelstein sichtbar ist."""
    if len(zustand.remembered_gems) > 0 or len(zustand.hypothetical_gems) > 0:
        return True
    else:
        return False


def check_if_destination_in_gems(zustand: Zustand):
    """Überprüft, ob sich an der Zielposition ein Edelstein befindet."""
    for gem in zustand.remembered_gems:
        if gem.position == zustand.destination:
            return True
    return False


def check_for_free_portal_places(zustand: Zustand):
    """Überprüft, ob es freie Plätze für Portale gibt angrenzend zum Bot."""
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    for dx, dy in dirs:
        nx = dx + zustand.bot[0]
        ny = dy + zustand.bot[1]
        if zustand.saved_matrix[ny][nx] == "X" and (nx, ny) not in zustand.any_portals:
            return True
    return False


def check_if_path_blocked(zustand: Zustand):
    """Überprüft, ob der gegebene Pfad durch Wände blockiert ist."""
    for pos in zustand.a_star_path:
        if (
            zustand.saved_matrix[pos[1]][pos[0]] == "X"
            and pos not in zustand.any_full_portals
        ):
            return True
    return False
