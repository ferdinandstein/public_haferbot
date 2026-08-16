from dataclasses import dataclass, fields, field
from typing import List, Literal, Dict, Set


@dataclass(init=False, slots=True)
class Gem:
    position: tuple
    ttl: int

    def __init__(self, position: list, ttl: int):
        self.position = tuple(position)
        self.ttl = ttl


@dataclass()
class Antenna:
    position: tuple
    signal: float

    def __init__(self, position: tuple, signal: float):
        self.position = position
        self.signal = signal


@dataclass(init=False)
class Config:
    width: int = None
    height: int = None
    vis_radius: int = None
    gem_ttl: int = None
    max_gems: int = None
    max_ticks: int = None
    bot_seed: int = None
    gem_spawn_rate: float = None
    signal_radius: int = None
    signal_cutoff: float = None
    signal_noise: float = None
    signal_quantization: float = None
    signal_fade: float = None
    max_antennas: int = None

    def __init__(self, **kwargs):
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)


@dataclass
class Zustand:
    # First Tick
    debug_enabled: bool = True
    config: Config = None
    permutations = []
    wall_offsets: Dict = field(default_factory=dict)

    # Aus deer data jeden tick
    tick: int = 0
    bot: tuple = None
    opponent: tuple = None
    opponent_area: set = None
    locked: bool = False
    locked_in: int = None
    last_opponent: tuple = None
    opponent_emoji: str = ""
    walls: List[tuple] = None
    floors: Set[tuple] = None
    signal_level: float = 0.0
    last_signal: float = 0.0
    antennas: List[Antenna] = None
    antennas_left: int = None
    visible_antennas: List[tuple] = None
    initative: bool = False
    with_opponent: bool = None
    my_points: int = 0
    opponent_points: int = 0
    total_gems_ttl: int = 0

    # Pfadplanungszeug
    destination: tuple = (0, 0)
    a_star_path: List[tuple] = None
    mid: tuple = None
    distances_to_bot: Dict[tuple, int] = field(default_factory=dict)
    circling: bool = False

    # Listen
    current_matrix: list = field(default_factory=list)
    saved_matrix: list = field(default_factory=list)

    visible_gems: List[Gem] = field(default_factory=list)
    last_visible_gems: List[Gem] = field(default_factory=list)
    remembered_gems = []
    last_remembered_gems = []

    # Frontier Zeug
    frontiers: List[tuple] = None
    saved_frontiers: List[tuple] = None
    clusters: list = field(default_factory=list)
    known_tiles = []
    unknown_tiles = None
    penaltys = {}
    wall_distance_cache = None

    dictionary_of_all_tiles = {}
    start_time = None
    last_move: Literal["N", "S", "E", "W", "WAIT"] = None

    # Signal zeug
    candidates = [set(), set()]
    spawn_ticks = [-1, -1]
    possible_pairs = []
    notfound = 0
    error_margin: float = 0.0

    candidates_by_antenna = []
    hypothetical_gems: List[Gem] = field(default_factory=list)
    last_hypothetical_gems: List[Gem] = field(default_factory=list)
    last_antennas: List[Antenna] = None
    dictionary_of_signals_and_stuff = {}
    possible_fields = None
    highest_field = None
    highest_signal = None
    highest_fields = None

    # Unsinniges Zeug
    messaged: bool = False
    messages = {
        "🧭": "Guten Tag Luto!",
        "🍪": "Aaaah ich muss gegen mich selbst spielen!",
        "🍋": "Auf ein gutes Match Zitronenbot!",
        "Ni": "Irgendwie denke ich immer wenn ich das Emoji lese an Pi...",
        "🤘": "Mensch es ist ja schon Open-League!",
        "🥷": "Mensch es ist ja schon Open-League!",
        "🦉": "Mensch es ist ja schon Open-League!",
        "🥵": "Mensch es ist ja schon Open-League!",
        "🐑": "Hallo langes Schaf!",
        "🐣": "Guten Tag Hatchling Hunter!",
        "😮": "😮 Ist das der Buffo?!",
        "🤑": "Hallo Dagobot!",
        "🦋": "Auf ein gutes Spiel!",
        "🧠": "Puh wen seh ich denn da?",
        "🃏": "Hallo Arti. Ich würde dir den Sieg gönnen!",
        "🧏": "Hallo BetaGem 76",
    }

    run_time_analyse: list = field(default_factory=list)
