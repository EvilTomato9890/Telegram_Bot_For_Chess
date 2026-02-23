"""Router factories."""

from .arbitrator import build_arbitrator_router
from .common import build_common_router
from .organizer import build_organizer_router
from .player import build_player_router

__all__ = [
    "build_common_router",
    "build_player_router",
    "build_arbitrator_router",
    "build_organizer_router",
]

