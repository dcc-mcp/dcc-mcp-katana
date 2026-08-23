"""Install SOP service coordinating Katana-owned preflight and resources."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from dcc_mcp_core.install_lifecycle import wait_for_sidecar_ready

from .__version__ import __version__
from .install_contract import (
    EXIT_PREFLIGHT,
    SCHEMA_VERSION,
    InstallFailure,
    empty_verify,
    runtime_core_version,
)
from .install_environment import (
    inspect_install,
    install_launcher,
    launcher_command,
    launcher_path,
    receipt_path,
    resource_step,
    uninstall_launcher,
)
from .install_host import (
    katana_version,
    python_import_check,
    resolve_katana,
    resolve_python,
    target_versions,
)


def plan(
    verb: str,
    dcc_path: Optional[Path],
    python_value: Optional[Path],
) -> dict[str, Any]:
    executable = resolve_katana(dcc_path)
    python = resolve_python(python_value, executable)
    host_version = katana_version(executable)
    versions = target_versions(python)
    target_adapter_version = versions["dcc-mcp-katana"]
    if target_adapter_version != __version__:
        raise InstallFailure(
            EXIT_PREFLIGHT,
            "adapter",
            (
                f"Target Python has dcc-mcp-katana {target_adapter_version}; "
                f"the installer is {__version__}"
            ),
        )
    environment = resource_step()
    inspection = inspect_install(__version__)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "planned",
        "dcc_type": "katana",
        "verb": verb,
        "adapter_version": __version__,
        "core_version": versions["dcc-mcp-core"],
        "target_adapter_version": target_adapter_version,
        "python_version": versions["python_version"],
        "katana_version": host_version,
        "dcc_path": str(executable),
        "python": str(python),
        "installation_state": inspection["installation_state"],
        "steps": [
            {"id": "preflight", "status": "ok", "katana_version": host_version},
            {"id": "resolve-python", "status": "ok", "path": str(python)},
            environment,
            {"id": verb, "status": "planned"},
        ],
        "next_steps": [],
        "receipt_path": str(receipt_path()),
        "verify": empty_verify(),
    }


def status_report() -> dict[str, Any]:
    inspection = inspect_install(__version__)
    state = inspection["installation_state"]
    action = "verify" if state == "current" else "install"
    if state == "upgrade":
        action = "upgrade"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "dcc_type": "katana",
        "verb": "status",
        "adapter_version": __version__,
        "core_version": runtime_core_version(),
        "installation_state": state,
        "checks": inspection["checks"],
        "receipt_path": str(receipt_path()),
        "launcher_path": str(launcher_path()),
        "steps": [{"id": "inspect-install", "status": "ok"}],
        "next_steps": [
            {
                "id": action,
                "description": f"Run {action} for the Katana adapter",
                "command": [
                    "dcc-mcp-katana",
                    action,
                    "--json",
                    *([] if action == "verify" else ["--yes"]),
                ],
                "why": f"The detected installation state is {state}",
            }
        ],
        "verify": empty_verify(),
    }


def uninstall_report(dry_run: bool) -> dict[str, Any]:
    inspection = inspect_install(__version__)
    step: dict[str, object]
    if dry_run:
        step = {
            "id": "remove-katana-launcher",
            "status": "planned",
            "changed": inspection["installation_state"] != "fresh",
        }
        status = "planned"
        state = inspection["installation_state"]
    else:
        step = uninstall_launcher()
        status = "ok"
        state = "fresh"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "dcc_type": "katana",
        "verb": "uninstall",
        "adapter_version": __version__,
        "core_version": runtime_core_version(),
        "installation_state": state,
        "receipt_path": str(receipt_path()),
        "launcher_path": str(launcher_path()),
        "steps": [step],
        "next_steps": [],
        "verify": empty_verify(),
    }


def verify_report(python_value: Optional[Path], timeout: float) -> dict[str, Any]:
    inspection = inspect_install(__version__)
    result: dict[str, Any] = {
        "directly_usable": False,
        "failure_stage": None,
        "failure_reason": None,
        "artifact": {"success": False},
        "import": {"success": False},
        "readiness": {"success": False},
    }
    if inspection["installation_state"] != "current":
        result.update(
            failure_stage="artifact",
            failure_reason=(
                f"Install receipt and launcher are not current: {inspection['installation_state']}"
            ),
        )
    else:
        result["artifact"] = {"success": True, **inspection["checks"]}
        receipt = inspection["receipt"]
        configured_python = python_value or Path(str(receipt.get("python", "")))
        result["import"] = python_import_check(configured_python.expanduser().resolve())
        if not result["import"].get("success"):
            result.update(
                failure_stage="import",
                failure_reason=result["import"].get("reason", "Target import failed"),
            )
        else:
            readiness = wait_for_sidecar_ready(
                dcc_type="katana",
                timeout_secs=max(0.0, timeout),
                probe_tool="katana_nodegraph__get_status",
            )
            result["readiness"] = readiness
            if not readiness.get("success"):
                result.update(
                    failure_stage="readiness",
                    failure_reason=readiness.get("message", "Katana adapter is not ready"),
                )
            else:
                result["directly_usable"] = True
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok" if result["directly_usable"] else "failed",
        "dcc_type": "katana",
        "verb": "verify",
        "adapter_version": __version__,
        "core_version": runtime_core_version(),
        "installation_state": inspection["installation_state"],
        "receipt_path": str(receipt_path()),
        "launcher_path": str(launcher_path()),
        "steps": [
            {
                "id": "verify-to-usable",
                "status": "ok" if result["directly_usable"] else "failed",
            }
        ],
        "next_steps": [] if result["directly_usable"] else status_report()["next_steps"],
        "verify": result,
    }


def apply_install(report: dict[str, Any]) -> dict[str, Any]:
    environment = install_launcher(report)
    report["status"] = "ok"
    report["installation_state"] = "current"
    report["launcher_path"] = str(launcher_path())
    report["receipt_path"] = str(receipt_path())
    report["steps"] = [
        environment if step["id"] == "persist-katana-resources" else step
        for step in report["steps"]
    ]
    report["steps"][-1]["status"] = "installed"
    report["next_steps"] = [
        {
            "id": "launch-katana",
            "description": "Launch Katana with the adapter resource path",
            "command": launcher_command(),
            "why": "Katana reads KATANA_RESOURCES only when the host process starts",
        }
    ]
    return report
