from include.zustand import Zustand


def check_for_change_gems(zustand: Zustand):
    if zustand.remembered_gems == zustand.last_remembered_gems and zustand.hypothetical_gems == zustand.last_hypothetical_gems:
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
    for gem in zustand.remembered_gems:
        if gem.position == zustand.destination:
            return True
    return False
