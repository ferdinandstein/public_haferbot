from dataclasses import dataclass, fields, field
from typing import List, Literal, Dict, Set


@dataclass(init=False)
class Position:
    x: int = None
    y: int = None

    def __init__(self, coordinates: list):
        self.x = coordinates[0]
        self.y = coordinates[1]

    def __sub__(self, other):
        return abs(self.x - other.x) + abs(self.y - other.y)

    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        if isinstance(other, Position):
            return self.x == other.x and self.y == other.y
        return False


@dataclass(init=False)
class Gem:
    position: Position = None
    ttl: int = None

    def __init__(self, position: list, ttl: int):
        self.position = Position(position)
        self.ttl = ttl


@dataclass()
class Node:
    position: Position = None
    g_cost: int = None
    h_cost: int = None
    f_cost: int = None
    parent: any = None
    unknown_streak = 0


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

    def __init__(self, **kwargs):
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)


@dataclass
class Zustand:
    config: Config = None
    tick: int = 0
    bot: Position = None
    opponent: Position = None
    last_opponent: Position = None
    opponent_emoji: str = ""
    walls: List[Position] = None
    floors: List[Position] = None
    destination: Position = None
    known_tiles = []

    debug_enabled: bool = False

    current_matrix: list = field(default_factory=list)
    saved_matrix: list = field(default_factory=list)

    visible_gems: List[Gem] = field(default_factory=list)
    modified_gems: List[Gem] = field(default_factory=list)
    remembered_gems: List[Gem] = field(default_factory=list)
    last_remembered_gems: List[Gem] = field(default_factory=list)
    frontiers: List[Position] = None
    saved_frontiers: List[Position] = None
    clusters: list = field(default_factory=list)
    last_clusters: List[List[Position]] = None
    initative: bool = False
    a_star_path: List[Position] = None
    dictionary_of_all_tiles = {}
    start_time = None
    last_move: Literal["N", "S", "E", "W", "WAIT"] = None
    with_opponent: bool = None

    signal_level: float = 0.0
    signal_level_dict: Dict[int, float] = field(default_factory=dict)
    current_candidates = {}
    last_candidates = {}
    possible_points = {}
    mid: Position = None

    circling = False
    discovered_in_tick_A: int = 0
    discovered_in_tick_B: int = 0
    discovered_in_tick_C: int = 0

    last_residual: float = 0.0
    possible_pairs = []
    last_possible_pairs = []
    possible_triples = []
    possible_swaps = []
    signal_offsets: Dict = field(default_factory=dict)
    distances_to_bot: Dict[Position, int] = field(default_factory=dict)
    run_time_analyse: list = field(default_factory=list)
    possible_duos = []

    messaged: bool = False
    messages = {
        "🧵": "Guten Tag Luto!",
        "🍪": "Aaaah ich muss gegen mich selbst spielen!",
        "🍋": "Auf ein gutes Match Zitronenbot! Möge der Bessere gewinnen!",
        "Ni": "Irgendwie denke ich immer wenn ich das Emoji lese an Pi...",
        "🤘": "Mensch es ist ja schon Open-League!",
        "😮": "😮 Ist das der Buffo?!",
        "🤑": "Lieber Dagobert gibst du mir bitte ein paar Gems von deinen Millionen ab???",
        "🧠": "Puh wen seh ich denn da?",
    }
