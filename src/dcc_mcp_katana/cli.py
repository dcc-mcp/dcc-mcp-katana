"""Small installation diagnostics CLI for the in-host Katana adapter."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional, Sequence

from .__version__ import __version__
from .bootstrap import bootstrap_error_summary
from .install_contract import (
    EXIT_INSTALL,
    EXIT_REQUIRES_RESTART,
    EXIT_VERIFY,
    LIFECYCLE_VERBS,
    SCHEMA_VERSION,
    InstallFailure,
    empty_verify,
    runtime_core_version,
)
from .install_environment import resource_entries, resource_path
from .install_lifecycle import (
    apply_install,
    plan,
    status_report,
    uninstall_report,
    verify_report,
)


def doctor_report() -> dict[str, object]:
    resource = resource_path()
    plugin = resource / "Plugins" / "dcc_mcp_katana.py"
    catalog = Path(__file__).resolve().parent / "skills" / "katana-nodegraph" / "tools.yaml"
    configured_entries = resource_entries(os.environ.get("KATANA_RESOURCES", ""))
    resource_resolved = resource.resolve(strict=False)
    bootstrap_errors = bootstrap_error_summary()
    last_bootstrap = bootstrap_errors["last"]
    checks = {
        "plugin_entry_exists": plugin.is_file(),
        "skill_catalog_exists": catalog.is_file(),
        "katana_resources_configured": bool(configured_entries),
        "resource_path_active": resource_resolved in configured_entries,
        "bootstrap_error_free": last_bootstrap is None or bool(last_bootstrap.get("success")),
    }
    return {
        "package": "dcc-mcp-katana",
        "version": __version__,
        "resource_path": str(resource),
        "checks": checks,
        "bootstrap_errors": bootstrap_errors,
        "ready": all(checks.values()),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dcc-mcp-katana")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("resource-path", help="Print the directory to add to KATANA_RESOURCES")
    doctor = subparsers.add_parser("doctor", help="Validate package resources and environment")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    for verb in sorted(LIFECYCLE_VERBS):
        lifecycle = subparsers.add_parser(verb, help=f"{verb.title()} the Katana adapter")
        lifecycle.add_argument("--dcc-path", type=Path)
        lifecycle.add_argument("--python", type=Path, dest="python_value")
        lifecycle.add_argument("--json", action="store_true", dest="as_json")
        lifecycle.add_argument("--yes", action="store_true")
        lifecycle.add_argument("--dry-run", action="store_true")
        lifecycle.add_argument("--timeout", type=float, default=10.0)
    return parser


def _print_lifecycle(report: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, sort_keys=True))
        return
    print(f"{report['verb']}: {report['status']}")
    for step in report.get("steps", []):
        print(f"{step['status'].upper()} {step['id']}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "resource-path":
        print(resource_path())
        return 0
    if args.command in LIFECYCLE_VERBS:
        try:
            if args.command == "status":
                report = status_report()
                _print_lifecycle(report, args.as_json)
                return 0
            if args.command == "verify":
                report = verify_report(args.python_value, args.timeout)
                _print_lifecycle(report, args.as_json)
                return 0 if report["verify"]["directly_usable"] else EXIT_VERIFY
            if args.command == "uninstall":
                if not args.dry_run and not args.yes:
                    raise InstallFailure(
                        EXIT_INSTALL,
                        "confirmation",
                        "Use --yes to uninstall the Katana integration",
                    )
                report = uninstall_report(args.dry_run)
                _print_lifecycle(report, args.as_json)
                return 0
            report = plan(args.command, args.dcc_path, args.python_value)
            if not args.dry_run and not args.yes:
                raise InstallFailure(
                    EXIT_INSTALL,
                    "confirmation",
                    "Use --yes to apply the planned lifecycle changes",
                )
            if not args.dry_run and args.command in {"install", "upgrade"}:
                report = apply_install(report)
            elif not args.dry_run:
                raise InstallFailure(
                    EXIT_INSTALL,
                    "apply",
                    f"{args.command} is not implemented yet",
                )
        except InstallFailure as exc:
            next_steps = []
            if exc.exit_code == EXIT_REQUIRES_RESTART:
                retry_command = ["dcc-mcp-katana", args.command, "--yes", "--json"]
                if args.dcc_path is not None:
                    retry_command.extend(["--dcc-path", str(args.dcc_path)])
                if args.python_value is not None:
                    retry_command.extend(["--python", str(args.python_value)])
                next_steps = [
                    {
                        "id": "retry-after-host-exit",
                        "description": "Exit Katana and retry the lifecycle operation",
                        "command": retry_command,
                        "why": "Windows has locked an adapter-owned integration file",
                    }
                ]
            report = {
                "schema_version": SCHEMA_VERSION,
                "status": (
                    "requires_restart" if exc.exit_code == EXIT_REQUIRES_RESTART else "failed"
                ),
                "dcc_type": "katana",
                "verb": args.command,
                "adapter_version": __version__,
                "core_version": runtime_core_version(),
                "failure": {"stage": exc.stage, "reason": exc.reason},
                "steps": [],
                "next_steps": next_steps,
                "receipt_path": str(Path.home() / ".dcc-mcp" / "receipts" / "katana.json"),
                "verify": empty_verify(),
            }
            _print_lifecycle(report, args.as_json)
            return exc.exit_code
        _print_lifecycle(report, args.as_json)
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
