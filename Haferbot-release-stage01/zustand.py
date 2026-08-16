from dataclasses import dataclass, fields, field
from typing import List, Literal


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


@dataclass(init=False)
class Config:
    width: int = None
    height: int = None
    vis_radius: int = None
    max_gems: int = None
    bot_seed: int = None
    gem_spawn_rate: float = None

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
    walls: List[Position] = None
    floors: List[Position] = None
    destination: Position = None

    current_matrix: list = field(default_factory=list)
    saved_matrix: list = field(default_factory=list)
    real_matrix: list = field(default_factory=list)

    visible_gems: List[Gem] = None
    modified_gems: List[Gem] = None
    remembered_gems: List[Gem] = None
    last_remembered_gems: List[Gem] = None
    frontiers: List[Position] = None
    saved_frontiers: List[Position] = None
    real_frontiers: List[Position] = None
    clusters: list = field(default_factory=list)
    last_clusters: List[List[Position]] = None
    initative: bool = False
    a_star_path: List[Position] = None
    best_weight = 30
    dictionary_of_all_tiles = {}
    start_time = None
    last_move: Literal["N", "S", "E", "W", "WAIT"] = None
    with_opponent: bool = None
