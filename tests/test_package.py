import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dcc_mcp_katana import __version__


def test_version_metadata_is_synchronized():
    root = Path(__file__).parents[1]
    assert f'version = "{__version__}"' in (root / "pyproject.toml").read_text(encoding="utf-8")
    manifest = json.loads((root / ".release-please-manifest.json").read_text(encoding="utf-8"))
    assert manifest["."] == __version__


def test_bundled_assets_exist():
    package = Path(__file__).parents[1] / "src" / "dcc_mcp_katana"
    assert (package / "katana_plugin" / "Plugins" / "dcc_mcp_katana.py").is_file()
    assert (package / "skills" / "katana-nodegraph" / "tools.yaml").is_file()


def test_start_server_defers_port_resolution_to_core(monkeypatch):
    from dcc_mcp_katana import server as server_module

    ports = []
    stub = SimpleNamespace(
        is_running=False,
        register_builtin_actions=lambda: None,
        start=lambda: None,
        stop=lambda: None,
    )

    monkeypatch.setattr(server_module, "_server", None)
    monkeypatch.setattr(
        server_module,
        "_dispatcher",
        SimpleNamespace(install=lambda: None, uninstall=lambda: None),
    )
    monkeypatch.setattr(
        server_module, "KatanaMcpServer", lambda port=None: ports.append(port) or stub
    )
    monkeypatch.setenv("DCC_MCP_KATANA_PORT", "8765")

    server_module.start_server(0)
    server_module.stop_server()
    server_module.start_server()
    server_module.stop_server()

    assert ports == [0, None]


def test_start_failure_rolls_back_dispatcher(monkeypatch):
    from dcc_mcp_katana import server as server_module

    events = []
    monkeypatch.setattr(server_module, "_server", None)
    monkeypatch.setattr(
        server_module,
        "_dispatcher",
        SimpleNamespace(
            install=lambda: events.append("install"),
            uninstall=lambda: events.append("uninstall"),
        ),
    )

    def fail_constructor(_port=None):
        raise RuntimeError("constructor failed")

    monkeypatch.setattr(server_module, "KatanaMcpServer", fail_constructor)
    with pytest.raises(RuntimeError, match="constructor failed"):
        server_module.start_server()
    assert events == ["install", "uninstall"]
    assert server_module._server is None


def test_stop_failure_still_uninstalls_dispatcher(monkeypatch):
    from dcc_mcp_katana import server as server_module

    events = []

    def fail_stop():
        raise RuntimeError("stop failed")

    monkeypatch.setattr(server_module, "_server", SimpleNamespace(stop=fail_stop))
    monkeypatch.setattr(
        server_module,
        "_dispatcher",
        SimpleNamespace(uninstall=lambda: events.append("uninstall")),
    )
    with pytest.raises(RuntimeError, match="stop failed"):
        server_module.stop_server()
    assert events == ["uninstall"]
    assert server_module._server is None
