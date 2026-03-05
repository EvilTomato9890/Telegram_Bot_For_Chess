"""Backward-compatible alias module."""

from .acl_service import COMMAND_REGISTRY, AccessControlService

__all__ = ["AccessControlService", "COMMAND_REGISTRY"]

