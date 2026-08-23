"""Katana host and target-interpreter preflight I/O."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .install_contract import (
    EXIT_PREFLIGHT,
    MIN_CORE_VERSION,
    MIN_KATANA_MAJOR,
    InstallFailure,
    version_tuple,
)

_KATANA_VERSION = re.compile(r"\b(?:Katana\s+)?(\d+)\.(\d+)v(\d+)\b", re.IGNORECASE)


def resolve_katana(value: Optional[Path]) -> Path:
    configured = value
    if configured is None and os.environ.get("KATANA_ROOT"):
        configured = Path(os.environ["KATANA_ROOT"])
    if configured is None:
        discovered = shutil.which("katanaBin") or shutil.which("katana")
        configured = Path(discovered) if discovered else None
    if configured is None:
        raise InstallFailure(EXIT_PREFLIGHT, "katana", "Katana installation was not found")
    resolved = configured.expanduser().resolve()
    if resolved.is_dir():
        candidates = (
            resolved / "bin" / "katanaBin.exe",
            resolved / "bin" / "katanaBin",
            resolved / "katana",
            resolved / "katanaBin",
        )
        resolved = next((candidate for candidate in candidates if candidate.is_file()), resolved)
    if not resolved.is_file():
        raise InstallFailure(EXIT_PREFLIGHT, "katana", f"Katana executable not found: {resolved}")
    return resolved


def katana_version(executable: Path) -> str:
    try:
        completed = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallFailure(EXIT_PREFLIGHT, "katana_version", str(exc)) from exc
    match = _KATANA_VERSION.search(f"{completed.stdout}\n{completed.stderr}")
    if completed.returncode or match is None:
        raise InstallFailure(EXIT_PREFLIGHT, "katana_version", "Could not determine Katana version")
    if int(match.group(1)) < MIN_KATANA_MAJOR:
        raise InstallFailure(
            EXIT_PREFLIGHT,
            "katana_version",
            f"Katana {match.group(0)} is unsupported; Katana 6.0 or newer is required",
        )
    return f"{match.group(1)}.{match.group(2)}v{match.group(3)}"


def resolve_python(value: Optional[Path], executable: Path) -> Path:
    configured = value
    if configured is None and os.environ.get("DCC_MCP_INSTALL_PYTHON"):
        configured = Path(os.environ["DCC_MCP_INSTALL_PYTHON"])
    if configured is None:
        root = (
            executable.parent.parent
            if executable.parent.name.lower() == "bin"
            else executable.parent
        )
        candidates = (
            root / "bin" / "python.exe",
            root / "bin" / "python3",
            executable.with_name("python.exe"),
            Path(sys.executable),
        )
        configured = next((candidate for candidate in candidates if candidate.is_file()), None)
    if configured is None:
        raise InstallFailure(EXIT_PREFLIGHT, "python", "Katana Python was not found")
    resolved = configured.expanduser().resolve()
    if not resolved.is_file():
        raise InstallFailure(EXIT_PREFLIGHT, "python", f"Python interpreter not found: {resolved}")
    return resolved


def target_versions(python: Path) -> dict[str, str]:
    code = (
        "import importlib.metadata as m, json, platform; "
        "print(json.dumps({'python_version': platform.python_version(), "
        "'dcc-mcp-core': m.version('dcc-mcp-core'), "
        "'dcc-mcp-katana': m.version('dcc-mcp-katana')}))"
    )
    try:
        completed = subprocess.run(
            [str(python), "-c", code],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallFailure(EXIT_PREFLIGHT, "python", str(exc)) from exc
    if completed.returncode:
        details = completed.stderr.strip().splitlines()
        raise InstallFailure(
            EXIT_PREFLIGHT,
            "python",
            details[-1] if details else "Target package metadata query failed",
        )
    try:
        versions = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise InstallFailure(EXIT_PREFLIGHT, "python", "Invalid target Python metadata") from exc
    if not isinstance(versions, dict):
        raise InstallFailure(EXIT_PREFLIGHT, "python", "Target Python metadata must be an object")
    if version_tuple(str(versions.get("python_version", ""))) < (3, 9):
        raise InstallFailure(EXIT_PREFLIGHT, "python", "Python 3.9 or newer is required")
    core_version = str(versions.get("dcc-mcp-core", ""))
    if version_tuple(core_version) < version_tuple(MIN_CORE_VERSION):
        raise InstallFailure(
            EXIT_PREFLIGHT,
            "core",
            f"dcc-mcp-core {core_version} is unsupported; {MIN_CORE_VERSION} or newer is required",
        )
    return {str(key): str(item) for key, item in versions.items()}


def python_import_check(python: Path) -> dict[str, object]:
    if not python.is_file():
        return {"success": False, "reason": f"Python interpreter not found: {python}"}
    code = (
        "import dcc_mcp_katana, json; "
        "print(json.dumps({'success': True, 'version': dcc_mcp_katana.__version__}))"
    )
    try:
        completed = subprocess.run(
            [str(python), "-c", code],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"success": False, "reason": str(exc)}
    if completed.returncode:
        details = completed.stderr.strip().splitlines()
        return {
            "success": False,
            "reason": details[-1] if details else "Target import failed",
        }
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        return {"success": False, "reason": "Invalid target import response"}
    if not isinstance(payload, dict) or not payload.get("success"):
        return {"success": False, "reason": "Target import did not report success"}
    return payload
