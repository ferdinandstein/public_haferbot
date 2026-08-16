from dataclasses import dataclass, fields, field
from typing import List, Literal, Dict, Set


@dataclass(init=False, slots=True)
class Gem:
    position: tuple
    ttl: int
    channel: int

    def __init__(self, position: list, ttl: int, channel: int = -1):
        self.position = tuple(position)
        self.ttl = ttl
        self.channel = channel


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
    # First Tick
    debug_enabled: bool = False
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
    signal_channels = []
    last_signal_channels = []
    initative: bool = False
    with_opponent: bool = None
    my_points: int = 0
    opponent_points: int = 0
    total_gems_ttl: int = 0

    # Pfadplanungszeug
    destination: tuple = None
    a_star_path: List[tuple] = None
    mid: tuple = None
    distances_to_bot: Dict[tuple, int] = field(default_factory=dict)

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
    candidates = []
    reseted_channels = []
    discovered_in_tick = []
    hypothetical_gems: List[Gem] = field(default_factory=list)
    last_hypothetical_gems: List[Gem] = field(default_factory=list)
    last_used_gems: List[Gem] = field(default_factory=list)

    # Unsinniges Zeug
    messaged: bool = False
    messages = {
        "😔": "Guten Tag Luto!",
        "🍪": "Aaaah ich muss gegen mich selbst spielen!",
        "🍋": "Auf ein gutes Match Zitronenbot! Möge der Bessere gewinnen!",
        "Ni": "Irgendwie denke ich immer wenn ich das Emoji lese an Pi...",
        "🤘": "Mensch es ist ja schon Open-League!",
        "🥷": "Mensch es ist ja schon Open-League!",
        "🦉": "Mensch es ist ja schon Open-League!",
        "🐑": "Hallo langes Schaf!",
        "🐣": "Guten Tag Hatchling Hunter!",
        "😮": "😮 Ist das der Buffo?!",
        "🤑": "So Dagobot Duck. Mal schauen wer heute gewinnt.",
        "🦋": "Auf ein gutes Rückspiel!",
        "🧠": "Puh wen seh ich denn da?",
    }

    run_time_analyse: list = field(default_factory=list)
