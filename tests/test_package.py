import json
from pathlib import Path

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
    from types import SimpleNamespace

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
