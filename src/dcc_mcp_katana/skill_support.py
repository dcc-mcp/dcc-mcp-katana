"""Shared result handling for Katana typed skill entry points."""

from __future__ import annotations

from typing import Any, Callable

from dcc_mcp_core.skill import skill_error, skill_success

from .operations import KatanaOperationError


def invoke(message: str, callback: Callable[..., dict[str, Any]], **kwargs: Any):
    """Execute one validated operation and return a stable DCC-MCP result."""

    try:
        payload = callback(**kwargs)
    except KatanaOperationError as error:
        return skill_error("Katana request rejected.", str(error))
    except Exception as error:
        return skill_error("Katana operation failed.", f"{type(error).__name__}: {error}")
    return skill_success(message, **payload)
