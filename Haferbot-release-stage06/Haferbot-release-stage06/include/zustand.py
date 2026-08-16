from dataclasses import dataclass, fields, field
from typing import List, Literal, Dict, Set


@dataclass(init=False, slots=True)
class Gem:
    """Repräsentiert ein Gem mit seiner Position, verbleibenden Lebensdauer (TTL) und optionalem Kanal, falls er durch ein Signal identifiziert wurde, sowie Nodes und ob noch verfügbar"""

    position: tuple
    ttl: int
    channel: int
    type_: str
    nodes: list
    taken: bool

    def __init__(
        self,
        position: list,
        ttl: int,
        type: str,
        channel: int = -1,
        nodes: list = [],
        taken: bool = False,
    ):
        self.position = tuple(position)
        self.ttl = ttl
        # "swarm" for swarm gem, "regular" for normal gem
        self.type_ = type
        self.channel = channel
        self.nodes = nodes
        self.taken = taken


@dataclass(init=False)
class Config:
    """Enthält die Konfiguration des Spiels, die zu Beginn der Runde übergeben wird."""

    # Nummer des Bots
    bot_id: int = None
    width: int = None
    height: int = None
    vis_radius: int = None
    gem_ttl: int = None
    swarm_gem_ttl: int = None
    max_gems: int = None
    max_ticks: int = None
    bot_seed: int = None
    gem_spawn_rate: float = None
    signal_radius: int = None
    signal_cutoff: float = None
    signal_fade: float = None
    swarm_node_count: int = None
    swarm_required_nodes: int = None
    swarm_score_two_nodes: float = None
    swarm_score_three_nodes: float = None

    # Anzahl der Teams
    team_count: int = None

    def __init__(self, **kwargs):
        names = set([f.name for f in fields(self)])
        # Bekommt Attribute als Dictionary und filtert sich die raus, die es hat.
        for k, v in kwargs.items():
            if k in names:
                setattr(self, k, v)
            elif k == "slot":
                setattr(self, "bot_id", v)


@dataclass(init=False)
class Weights:
    """Enthält die Gewichtungen für verschiedene Faktoren, die in der Entscheidungsfindung des Bots berücksichtigt werden."""

    # Weigths in Bot
    search_till_tick: int = 2000
    # Weights in Clustering
    c_best_age: int = 300
    c_tile_weight = 2
    c_dist_weight = 4
    c_age_weight = 5
    c_cluster_and_total_weight = 2
    c_w = 0.3
    c_total_cluster_dist_weight = 4
    c_tile_weight_cluster_score = 3
    # Mid computing weights
    m_unknown_scale = 0.7
    # Astar weights
    a_risk_factor_low = 0.2
    a_risk_factor_high = 2.4
    a_streak_weigth = 1.95
    a_unknown_and_wall_penalty = 4
    a_opponent_penalty = 3
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
    # Buffer weights
    b_max_Swarm_gem_dist = 70
    b_max_swarm_gem_awaiting = 120
    b_alarm_dist = 13
    b_alarm_duration = 8


@dataclass
class Zustand:
    """Repräsentiert den aktuellen Zustand des Spiels,
    der in jedem Tick aktualisiert wird und alle relevanten Informationen über die aktuelle Spielsituation enthält.
    """

    # Ein "last" bedeutet, dass es aus dem letzten Tick die Info ist
    # First Tick
    debug_enabled: bool = False
    config: Config = None
    permutations = []
    wall_offsets: Dict = field(default_factory=dict)
    weights: Weights = None

    # Aus der data jeden tick
    tick: int = 0
    # Aktueller Tick, davor und vor dem davor
    bot: tuple = None
    last_bot: tuple = None
    last_last_bot: tuple = None

    opponents: List[tuple] = None
    locked: bool = False
    # Tick in dem gelockt wurde
    locked_in: int = None
    opponent_emoji: str = ""
    walls: List[tuple] = None
    floors: Set[tuple] = None
    # Gesamt Signal
    signal_level: float = 0.0
    signal_channels = []
    last_signal_channels = []
    # Zählt wie lange kein Signal auf Kanal war
    no_signal_streak: list = field(default_factory=list)
    initative: bool = False
    with_opponent: bool = None
    # Punktezählung
    my_points: int = 0
    opponent_points: int = 0
    total_gems_ttl: int = 0

    # Pfadplanungszeug
    destination: tuple = None
    # Eine Liste der Pfadpositionen
    a_star_path: List[tuple] = None

    mid: tuple = None
    # Distanzen von jedem Feld zum Bot
    distances_to_bot: Dict[tuple, int] = field(default_factory=dict)

    teammates: list = field(default_factory=list)

    # Karte die zum erkunden auch mal resettet wird (nicht genutzt)
    current_matrix: list = field(default_factory=list)
    # Gespeicherte Karte
    saved_matrix: list = field(default_factory=list)
    # Geteilte Karte
    shared_matrix: list = field(default_factory=list)

    visible_gems: List[Gem] = field(default_factory=list)
    last_visible_gems: List[Gem] = field(default_factory=list)

    # Gemerkte Gems
    remembered_gems = []
    last_remembered_gems = []

    # Frontier Zeug
    frontiers: List[tuple] = None
    saved_frontiers: List[tuple] = None

    known_tiles = []
    unknown_tiles = None
    penaltys = {}
    wall_distance_cache = None

    # Bewegung ohne Gem
    checked_matrix: list = field(default_factory=list)
    cutoff_dist: float = None

    # Für den gesamten Tick die Zeitmessung
    start_time = None
    bits_per_point = []

    last_move: Literal["N", "S", "E", "W", "WAIT"] = None

    ## Signal zeug
    # Kandidaten pro Kanal
    candidates = []

    reseted_channels = []

    # Wann ist ein Gem auf einem Kanal gespawnt
    discovered_in_tick = []

    hypothetical_gems: List[Gem] = field(default_factory=list)
    last_hypothetical_gems: List[Gem] = field(default_factory=list)
    last_used_gems: List[Gem] = field(default_factory=list)

    # Zum feststellen, ob der Bot wackelt
    wobbling: bool = False
    wobbling_counter: int = 0

    # Buffer
    # Anfang: 4 x 3 Bits für Bot Offset

    # Binärer gesamter Buffer
    team_buffer: list = field(default_factory=list)

    # Liste von Gems im Buffer
    gems_in_buffer: list[Gem] = field(default_factory=list)

    # Gems die man selbst anläuft
    gems_taken: list[Gem] = field(default_factory=list)

    msgs_written: list = field(default_factory=list)
    msgs_in_buffer: list = field(default_factory=list)

    node_offset_to_bin: dict = field(default_factory=dict)
    bin_to_node_offset: dict = field(default_factory=dict)

    map_update: str = ""
    turn: int = 3
    bits_left: int = 0
    open_request: str = ""
    open_request_channel: int = -1

    approved_swarm_gem: list = field(default_factory=list)
    is_there_an_open_request: bool = False

    gems_and_nodes: dict = field(default_factory=dict)
    accepted_request: bool = False
    approved_gem_channel: int = -1

    offset: bool = True

    used_swarm_gems: list = field(default_factory=list)

    # Opponent: Tick last seen
    opponents_on_nodes: list = field(default_factory=dict)

    alarmed = (False, 0)

    # Anderes Zeug
    # Begrüzungen an die Gegner
    messaged: bool = False
    mg_1 = "Mensch es ist ja schon Open-League!"
    messages = {
        "🧠": "Puh wen seh ich denn da?",
        "🍪": "Aha wir müssen gegen uns selbst spielen!",
        "🦎": "Hallo ᓬ(•ᴗ•)ᕒ",
        "🥷": "Auf ein faires Spiel Nakamura",
        "Ni": "Irgendwie denke ich immer wenn ich das Emoji lese an Pi...",
        "🥵": mg_1,
        "🦉": "Grüß dich Path🦉ogic",
        "😮": "😮 Ist das der Buffo?!",
        "🏹": "Auf ein gutes Spiel Gem Hunter!",
        "🦋": "Auf ein gutes Spiel!",
        "🐑": "Hallo lange 🐑🐑!",
        "💠": "Hallo GemSpectre",
        "🚆": "Tuuuuut!",
        "💀": mg_1,
        "🍋": "Auf ein gutes Match Zitronenbot!",
        "☀": "Warum gibt es zwei Stollentrolle?",
        "🐉": "Tag Gem Fly",
        "🐍": "There is a Snake in the Maze!",
        "🤖": "Hallo NimVek",
        "☣": "Warum gibt es zwei Stollentrolle?",
        "🦀": "Hallo RustyClanker",
        "⛏": "Hallo Ģem DiggeɌ",
    }

    run_time_analyse: list = field(default_factory=list)
    test = []
