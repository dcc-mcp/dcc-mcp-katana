"""Small installation diagnostics CLI for the in-host Katana adapter."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional, Sequence

from .__version__ import __version__


def resource_path() -> Path:
    return Path(__file__).resolve().parent / "katana_plugin"


def doctor_report() -> dict[str, object]:
    resource = resource_path()
    plugin = resource / "Plugins" / "dcc_mcp_katana.py"
    catalog = Path(__file__).resolve().parent / "skills" / "katana-nodegraph" / "tools.yaml"
    configured_entries = [
        Path(value).expanduser().resolve(strict=False)
        for value in os.environ.get("KATANA_RESOURCES", "").split(os.pathsep)
        if value.strip()
    ]
    resource_resolved = resource.resolve(strict=False)
    checks = {
        "plugin_entry_exists": plugin.is_file(),
        "skill_catalog_exists": catalog.is_file(),
        "katana_resources_configured": bool(configured_entries),
        "resource_path_active": resource_resolved in configured_entries,
    }
    return {
        "package": "dcc-mcp-katana",
        "version": __version__,
        "resource_path": str(resource),
        "checks": checks,
        "ready": all(checks.values()),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dcc-mcp-katana")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("resource-path", help="Print the directory to add to KATANA_RESOURCES")
    doctor = subparsers.add_parser("doctor", help="Validate package resources and environment")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "resource-path":
        print(resource_path())
        return 0
    report = doctor_report()
    if args.as_json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"dcc-mcp-katana {report['version']}")
        print(f"resource path: {report['resource_path']}")
        for name, passed in report["checks"].items():
            print(f"{'PASS' if passed else 'FAIL'} {name}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
