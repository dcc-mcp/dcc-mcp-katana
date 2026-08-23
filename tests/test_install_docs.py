from pathlib import Path


def test_install_runbook_is_complete_and_discoverable():
    root = Path(__file__).parents[1]
    runbook = root / "install.md"
    text = runbook.read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")

    for heading in (
        "## Requirements",
        "## Supported versions",
        "## Agent quick path",
        "## Manual path",
        "## Verify",
        "## Upgrade",
        "## Uninstall",
        "## Troubleshooting",
    ):
        assert heading in text
    for platform in ("Windows", "Linux", "macOS"):
        assert platform in text
    for command in (
        "dcc-mcp-katana install --dry-run --json",
        "dcc-mcp-katana install --yes --json",
        "dcc-mcp-katana status --json",
        "dcc-mcp-katana verify --json",
        "dcc-mcp-katana upgrade --yes --json",
        "dcc-mcp-katana uninstall --yes --json",
    ):
        assert command in text
    assert "KATANA_RESOURCES" in text
    assert ".dcc-mcp/receipts/katana.json" in text
    assert "https://raw.githubusercontent.com/dcc-mcp/dcc-mcp-katana/main/install.md" in text
    assert "[Install and upgrade](install.md)" in readme
