from dataclasses import dataclass, fields, field
from typing import List, Literal, Dict, Set


@dataclass(init=False, slots=True)
class Gem:
    """Repräsentiert ein Gem mit seiner Position, verbleibenden Lebensdauer (TTL) und optionalem Kanal, falls er durch ein Signal identifiziert wurde."""

    position: tuple
    ttl: int
    channel: int

    def __init__(self, position: list, ttl: int, channel: int = -1):
        self.position = tuple(position)
        self.ttl = ttl
        self.channel = channel


@dataclass(init=False)
class Config:
    """Enthält die Konfiguration des Spiels, die zu Beginn des Matches übergeben wird."""

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
    max_portals: int = None

    def __init__(self, **kwargs):
        names = set([f.name for f in fields(self)])
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)


@dataclass(init=False)
class Weights:
    """Enthält die Gewichtungen für verschiedene Faktoren, die in der Entscheidungsfindung des Bots berücksichtigt werden."""

    # Weigths in Bot
    max_dist_mid_portal: int = 20
    max_dist_border_portal: int = 10
    search_till_tick: int = 200
    # Weights in Clustering
    c_best_age: int = 200
    c_tile_weight = 2
    c_dist_weight = 4
    c_age_weight = 5
    c_cluster_and_total_weight = 2
    c_w = 0.3
    c_total_cluster_dist_weight = 4
    c_tile_weight_cluster_score = 3
    # Border Portal weights
    p_claimed_fields_min: float = 0
    p_dist_min: int = 0
    # Mid computing weights
    m_unknown_scale = 0.7
    # Astar weights
    a_risk_factor_low = 0.2
    a_risk_factor_high = 2.4
    a_streak_weigth = 1.95
    a_unknown_and_wall_penalty = 4
    a_opponent_penalty = 2
    # Folow astar weights
    f_min_diff = 1400
    f_max_fields_opponent = 30
    # Route planning weights
    r_teiler = 50
    r_exp = 1.8
    r_border = 50
    r_dist_points_factor = 0.5
    # Signal interpretation weights
    s_field_unknown_weight = 0.75
    s_error_margin: float = None


@dataclass
class Zustand:
    """Repräsentiert den aktuellen Zustand des Spiels,
    der in jedem Tick aktualisiert wird und alle relevanten Informationen über die aktuelle Spielsituation enthält.
    """

    # First Tick
    debug_enabled: bool = False
    config: Config = None
    permutations = []
    wall_offsets: Dict = field(default_factory=dict)
    weights: Weights = None

    # Aus deer data jeden tick
    tick: int = 0
    bot: tuple = None
    last_bot: tuple = None
    opponent: tuple = None
    opponent_area: set = None
    locked: bool = False
    locked_in: int = None
    last_opponent: tuple = None
    opponent_emoji: str = ""
    walls: List[tuple] = None
    floors: Set[tuple] = None
    visible_portals: List[tuple] = None
    portal_stubs: List[tuple] = None
    signal_level: float = 0.0
    signal_channels = []
    last_signal_channels = []
    initative: bool = False
    with_opponent: bool = None
    my_points: int = 0
    opponent_points: int = 0
    total_gems_ttl: int = 0
    #                 [id1:[[Portal1 von wo], [Portal2 von wo]], ...]
    portal_pairs: List[List[List[tuple]]] = field(default_factory=list)

    border_portals: List[List[tuple]] = field(default_factory=list)
    best_portals = None

    mid_portals: List[List[tuple]] = field(default_factory=list)

    # Von Portal1: EingangP2
    portal_teleportations: Dict[tuple, tuple] = field(default_factory=dict)
    # (From E1 to E2): P1
    e_e_p: Dict[tuple, tuple] = field(default_factory=dict)
    # Alle möglichen Potale + Stubs
    any_portals: Set[tuple] = field(default_factory=set)
    # Alle bekannten vollständigen Portale (ohne Stubs)
    any_full_portals: Set[tuple] = field(default_factory=set)
    # Keine Stubs nur die vollständigen vom Gegner
    unknown_opponent_portals: Set[tuple] = field(default_factory=set)
    went_through: bool = False
    solved_opponent_portals: List[tuple] = field(default_factory=list)

    known_opponent_portals: List[List[List[tuple]]] = field(default_factory=list)

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
    mg_1 = "Mensch es ist ja schon Open-League!"
    messages = {
        "🧭": "Guten Tag Luto!",
        "🍪": "Aaaah ich muss gegen mich selbst spielen!",
        "🍋": "Auf ein gutes Match Zitronenbot!",
        "Ni": "Irgendwie denke ich immer wenn ich das Emoji lese an Pi...",
        "🤘": mg_1,
        "🥷": mg_1,
        "🦉": "Grüß dich Path🦉ogic",
        "🥵": mg_1,
        "🐑": "Hallo lange 🐑🐑!",
        "🐣": "Guten Tag Hatchling Hunter!",
        "😮": "😮 Ist das der Buffo?!",
        "🤑": "Hallo Dagobot!",
        "🦋": "Auf ein gutes Spiel!",
        "🧠": "Puh wen seh ich denn da?",
        "🃏": "Hallo Arti!",
        "🧏": "Hallo SigmaGem 76",
    }

    run_time_analyse: list = field(default_factory=list)
    test = []
