from include.zustand import Zustand


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
                        (x, y): {
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
):  # C wieder Tabelle in zustand mit höhe weite initialisiert
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
                row.append("/")
        zustand.current_matrix.append(row)  # adding rows to the matrix


def initalize_saved_matrix(
    zustand: Zustand,
):  # C wieder Tabelle in zustand mit höhe weite initialisiert
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
                row.append("/")
        zustand.saved_matrix.append(row)  # adding rows to the matrix


def make_current_matrix(zustand: Zustand):

    for wall in zustand.walls:
        zustand.current_matrix[wall[1]][wall[0]] = "X"

    for floor in zustand.floors:
        zustand.current_matrix[floor[1]][floor[0]] = "0"


def make_saved_matrix(zustand: Zustand):
    changed = []
    for wall in zustand.walls:
        if zustand.saved_matrix[wall[1]][wall[0]] == "/":
            zustand.saved_matrix[wall[1]][wall[0]] = "X"
            changed.append(wall)

    for floor in zustand.floors:
        zustand.saved_matrix[floor[1]][floor[0]] = "0"

    return changed


def reset_matrix_floors(zustand: Zustand):
    y = 0
    for row in zustand.current_matrix:
        x = 0
        for col in row:
            if col == "0":
                zustand.current_matrix[y][x] = "/"
            x += 1
        y += 1


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
                    zustand.frontiers.append((x, y))
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
                    frontiers.append((x, y))

            x += 1
        y += 1
    zustand.saved_frontiers = frontiers
