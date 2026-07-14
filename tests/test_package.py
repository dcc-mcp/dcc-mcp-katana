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
