from include.zustand import Zustand


def initalize_current_matrix(
    zustand: Zustand,
):  # wieder Tabelle in zustand mit höhe weite initialisiert
    width = zustand.config.width
    height = zustand.config.height
    zustand.current_matrix = []

    for i in range(
        height
    ):  # für jedes element der höhe wird eine Zeile in der Tabelle gemacht
        row = []
        for j in range(
            width
        ):  # und für jedes Element der Breite ein / (bedeutet noch nicht bestimmt)
            if i == 0 or i == height - 1 or j == 0 or j == width - 1:
                row.append("X")  # Rand ist immer Wand
            else:
                row.append("/")
        zustand.current_matrix.append(row)  # adding rows to the matrix


def initalize_saved_matrix(
    zustand: Zustand,
):  # wieder Tabelle in zustand mit höhe weite initialisiert
    width = zustand.config.width
    height = zustand.config.height
    zustand.saved_matrix = []

    for i in range(
        height
    ):  # für jedes element der höhe wird eine Zeile in der Tabelle gemacht
        row = []
        for j in range(
            width
        ):  # und für jedes Element der Breite ein / (bedeutet noch nicht bestimmt)
            if i == 0 or i == height - 1 or j == 0 or j == width - 1:
                row.append("X")  # Rand ist immer Wand
            else:
                row.append("/")
        zustand.saved_matrix.append(row)  # adding rows to the matrix


def initalize_shared_matrix(
    zustand: Zustand,
):
    width = zustand.config.width
    height = zustand.config.height
    zustand.shared_matrix = []

    for i in range(height):
        row = []
        for j in range(width):
            if i == 0 or i == height - 1 or j == 0 or j == width - 1:
                row.append("X")  # Rand ist immer Wand
            else:
                row.append("/")
        zustand.shared_matrix.append(row)  # adding rows to the matrix


def make_current_matrix(zustand: Zustand):
    """Matrix updaten"""

    for wall in zustand.walls:
        zustand.current_matrix[wall[1]][wall[0]] = "X"

    for floor in zustand.floors:
        zustand.current_matrix[floor[1]][floor[0]] = "0"


def make_saved_matrix(zustand: Zustand):
    """Matrix updaten"""
    changed = []
    for wall in zustand.walls:
        if zustand.saved_matrix[wall[1]][wall[0]] == "/":
            zustand.saved_matrix[wall[1]][wall[0]] = "X"
            changed.append(wall)

    for floor in zustand.floors:
        zustand.saved_matrix[floor[1]][floor[0]] = "0"

    return changed


def reset_matrix_floors(zustand: Zustand):
    """Matrix '0' resetten auf '/'"""
    y = 0
    for row in zustand.current_matrix:
        x = 0
        for col in row:
            if col == "0":
                zustand.current_matrix[y][x] = "/"
            x += 1
        y += 1


def get_current_frontiers(zustand: Zustand):
    """Schnittstellen zwischen '/' und '0' bestimmen"""
    zustand.frontiers = []
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    y = 0
    for row in zustand.current_matrix:
        x = 0
        for col in row:
            if col == "0":
                for dx, dy in dirs:
                    nx, ny = dx + x, dy + y
                    if (
                        0 <= nx < zustand.config.width
                        and 0 <= ny < zustand.config.height
                        and zustand.current_matrix[ny][nx] == "/"
                    ):
                        zustand.frontiers.append((x, y))

            x += 1
        y += 1


def get_saved_frontiers(zustand: Zustand):
    """Schnittstellen zwischen '/' und '0' bestimmen"""
    frontiers = []
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    y = 0
    for row in zustand.saved_matrix:
        x = 0
        for col in row:
            if col == "0":
                for dx, dy in dirs:
                    nx, ny = dx + x, dy + y
                    if (
                        0 <= nx < zustand.config.width
                        and 0 <= ny < zustand.config.height
                        and zustand.current_matrix[ny][nx] == "/"
                    ):
                        zustand.frontiers.append((x, y))

            x += 1
        y += 1
    zustand.saved_frontiers = frontiers
