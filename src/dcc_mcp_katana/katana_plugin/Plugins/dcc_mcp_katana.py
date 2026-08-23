"""Katana resource plugin entry point with fail-safe bootstrap diagnostics."""

from dcc_mcp_katana.bootstrap import initialize_with_capture
from dcc_mcp_katana.plugin import initialize

initialize_with_capture(initialize)
