"""Katana MCP server lifecycle."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Optional

from dcc_mcp_core import DccServerOptions, HostExecutionBridge
from dcc_mcp_core.server_base import DccServerBase

from .__version__ import __version__
from .dispatcher import KatanaDispatcher

DEFAULT_PORT = 0
SERVER_NAME = "dcc-mcp-katana"
_dispatcher = KatanaDispatcher()
_server: Optional["KatanaMcpServer"] = None


class KatanaMcpServer(DccServerBase):
    """MCP server hosted by a running Katana session."""

    def __init__(self, port: Optional[int] = None) -> None:
        options = DccServerOptions.from_env(
            "katana",
            Path(__file__).resolve().parent / "skills",
            port=port,
            server_name=SERVER_NAME,
            server_version=__version__,
            execution_bridge=HostExecutionBridge(dispatcher=_dispatcher),
        )
        super().__init__(options=options)

    def _version_string(self) -> str:
        try:
            import KatanaInfo

            return str(KatanaInfo.version)
        except Exception:
            return "Katana"


def start_server(port: Optional[int] = None) -> KatanaMcpServer:
    """Install the native event handler and start the singleton server."""
    global _server
    if _server is not None and _server.is_running:
        return _server
    _dispatcher.install()
    candidate = None
    try:
        candidate = KatanaMcpServer(port)
        candidate.register_builtin_actions()
        candidate.start()
    except Exception:
        if candidate is not None:
            with suppress(Exception):
                candidate.stop()
        with suppress(Exception):
            _dispatcher.uninstall()
        raise
    _server = candidate
    return candidate


def stop_server() -> None:
    """Stop the server and remove the native event handler."""
    global _server
    try:
        if _server is not None:
            _server.stop()
    finally:
        _server = None
        _dispatcher.uninstall()
