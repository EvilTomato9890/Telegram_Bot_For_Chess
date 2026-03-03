"""Admin router composition."""

from __future__ import annotations

from aiogram import Router

from bot.context import RouterContext

from .organizer_participants import register_participant_handlers
from .organizer_shared import OrganizerShared
from .organizer_tables import register_table_handlers
from .organizer_tournament import register_tournament_handlers


def build_organizer_router(context: RouterContext) -> Router:
    """Create admin router and register split handler groups."""

    router = Router(name="organizer")
    shared = OrganizerShared(
        acl=context.acl_service,
        registration_service=context.registration_service,
        tournament_service=context.tournament_service,
        pairing_service=context.pairing_service,
        scoring_service=context.scoring_service,
        undo_service=context.undo_service,
        player_repo=context.player_repo,
        round_repo=context.round_repo,
        game_repo=context.game_repo,
        table_repo=context.table_repo,
        audit_logger=context.audit_logger,
        notification_service=context.notification_service,
        notification_gateway=context.notification_gateway,
    )
    register_participant_handlers(router, shared)
    register_table_handlers(router, shared)
    register_tournament_handlers(router, shared)
    return router

