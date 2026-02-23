"""Backward-compatible service aliases.

New code should import from dedicated modules in `services/`.
"""

from .acl_service import AccessControlService
from .notification_service import NotificationService
from .pairing_service import PairingService
from .registration_service import RegistrationService
from .result_service import ResultService
from .scoring_service import ScoringService
from .ticket_service import TicketService
from .tournament_service import TournamentService
from .undo_service import UndoService

__all__ = [
    "AccessControlService",
    "NotificationService",
    "PairingService",
    "RegistrationService",
    "ResultService",
    "ScoringService",
    "TicketService",
    "TournamentService",
    "UndoService",
]

