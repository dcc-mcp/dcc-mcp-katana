"""Katana resource-path and adapter-owned launcher persistence."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shlex
import tempfile
from pathlib import Path
from typing import Any

from .install_contract import (
    EXIT_INSTALL,
    EXIT_REQUIRES_RESTART,
    SCHEMA_VERSION,
    InstallFailure,
)


def resource_path() -> Path:
    return Path(__file__).resolve().parent / "katana_plugin"


def resource_entries(value: str) -> list[Path]:
    return [
        Path(item).expanduser().resolve(strict=False)
        for item in value.split(os.pathsep)
        if item.strip()
    ]


def receipt_path() -> Path:
    return Path.home() / ".dcc-mcp" / "receipts" / "katana.json"


def launcher_path() -> Path:
    suffix = ".cmd" if os.name == "nt" else ".sh"
    return Path.home() / ".dcc-mcp" / "launchers" / f"katana{suffix}"


def launcher_command() -> list[str]:
    launcher = str(launcher_path())
    if os.name == "nt":
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", launcher]
    return [launcher]


def resource_step() -> dict[str, object]:
    before = resource_entries(os.environ.get("KATANA_RESOURCES", ""))
    adapter_resource = resource_path().resolve(strict=False)
    after = list(before)
    if adapter_resource not in after:
        after.append(adapter_resource)
    return {
        "id": "persist-katana-resources",
        "status": "planned",
        "owner": "adapter-launcher",
        "before": [str(path) for path in before],
        "after": [str(path) for path in after],
        "changed": after != before,
    }


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _batch_literal(value: str) -> str:
    if any(character in value for character in ('"', "\r", "\n", "\0")):
        raise InstallFailure(EXIT_INSTALL, "launcher", "Unsafe character in launcher path")
    return value.replace("%", "%%")


def _launcher_payload(executable: Path) -> bytes:
    resource = str(resource_path().resolve(strict=False))
    if os.name == "nt":
        host = _batch_literal(str(executable))
        adapter_resource = _batch_literal(resource)
        content = (
            "@echo off\r\n"
            "setlocal DisableDelayedExpansion\r\n"
            "if defined KATANA_RESOURCES (\r\n"
            f'  set "KATANA_RESOURCES=%KATANA_RESOURCES%;{adapter_resource}"\r\n'
            ") else (\r\n"
            f'  set "KATANA_RESOURCES={adapter_resource}"\r\n'
            ")\r\n"
            f'"{host}" %*\r\n'
        )
    else:
        content = (
            "#!/bin/sh\n"
            'KATANA_RESOURCES="${KATANA_RESOURCES:+${KATANA_RESOURCES}:}"'
            f"{shlex.quote(resource)}\n"
            "export KATANA_RESOURCES\n"
            f'exec {shlex.quote(str(executable))} "$@"\n'
        )
    return content.encode("utf-8")


def _atomic_write(path: Path, payload: bytes, mode: int = 0o600) -> bool:
    if path.is_file() and path.read_bytes() == payload:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def load_receipt() -> dict[str, Any] | None:
    path = receipt_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallFailure(EXIT_INSTALL, "receipt", f"Invalid install receipt: {exc}") from exc
    if not isinstance(payload, dict):
        raise InstallFailure(EXIT_INSTALL, "receipt", "Install receipt must be a JSON object")
    return payload


def _receipt_owns_launcher(receipt: dict[str, Any] | None, launcher: Path) -> bool:
    if receipt is None:
        return False
    environment = receipt.get("environment")
    return bool(
        receipt.get("dcc_type") == "katana"
        and isinstance(environment, dict)
        and environment.get("owner") == "adapter-launcher"
        and environment.get("launcher_path") == str(launcher)
    )


def inspect_install(adapter_version: str) -> dict[str, Any]:
    launcher = launcher_path()
    receipt_file = receipt_path()
    receipt = load_receipt()
    receipt_valid = _receipt_owns_launcher(receipt, launcher)
    launcher_exists = launcher.is_file()
    expected_hash = None
    if receipt_valid:
        files = receipt.get("files", [])
        if isinstance(files, list):
            entry = next(
                (
                    item
                    for item in files
                    if isinstance(item, dict) and item.get("path") == str(launcher)
                ),
                None,
            )
            expected_hash = entry.get("sha256") if entry else None
    hash_matches = bool(
        launcher_exists
        and isinstance(expected_hash, str)
        and _sha256(launcher.read_bytes()) == expected_hash
    )
    version_current = bool(receipt_valid and receipt.get("adapter_version") == adapter_version)
    if receipt is None and not launcher_exists:
        state = "fresh"
    elif not receipt_valid or not launcher_exists:
        state = "partial"
    elif not hash_matches:
        state = "repair"
    elif not version_current:
        state = "upgrade"
    else:
        state = "current"
    return {
        "installation_state": state,
        "receipt": receipt,
        "checks": {
            "receipt_exists": receipt_file.is_file(),
            "launcher_exists": launcher_exists,
            "receipt_valid": receipt_valid,
            "launcher_hash_matches": hash_matches,
            "version_stamp_current": version_current,
        },
    }


def install_launcher(report: dict[str, Any]) -> dict[str, object]:
    """Atomically converge the owned launcher and receipt, rolling back on failure."""

    launcher = launcher_path()
    receipt_file = receipt_path()
    previous_receipt = load_receipt()
    if launcher.exists() and not _receipt_owns_launcher(previous_receipt, launcher):
        raise InstallFailure(
            EXIT_INSTALL,
            "launcher",
            f"Refusing to overwrite an unowned launcher: {launcher}",
        )
    previous_launcher = launcher.read_bytes() if launcher.is_file() else None
    previous_mode = launcher.stat().st_mode if launcher.is_file() else 0o700
    launcher_payload = _launcher_payload(Path(report["dcc_path"]))
    receipt_payload = {
        "schema_version": SCHEMA_VERSION,
        "dcc_type": "katana",
        "adapter_version": report["adapter_version"],
        "core_version": report["core_version"],
        "katana_version": report["katana_version"],
        "dcc_path": report["dcc_path"],
        "python": report["python"],
        "environment": {
            "owner": "adapter-launcher",
            "launcher_path": str(launcher),
            "resource_path": str(resource_path().resolve(strict=False)),
        },
        "files": [{"path": str(launcher), "sha256": _sha256(launcher_payload)}],
    }
    receipt_bytes = (json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n").encode()
    launcher_changed = False
    try:
        launcher_changed = _atomic_write(launcher, launcher_payload, 0o700)
        receipt_changed = _atomic_write(receipt_file, receipt_bytes)
    except (OSError, InstallFailure) as exc:
        try:
            if launcher_changed:
                if previous_launcher is None:
                    launcher.unlink(missing_ok=True)
                else:
                    _atomic_write(launcher, previous_launcher, previous_mode)
        except OSError as rollback_exc:
            raise InstallFailure(
                EXIT_INSTALL,
                "rollback",
                f"Install failed ({exc}); launcher rollback failed ({rollback_exc})",
            ) from rollback_exc
        if isinstance(exc, InstallFailure):
            raise
        if isinstance(exc, PermissionError):
            raise InstallFailure(
                EXIT_REQUIRES_RESTART,
                "launcher_locked",
                str(exc),
            ) from exc
        raise InstallFailure(EXIT_INSTALL, "install", str(exc)) from exc
    return {
        "id": "persist-katana-resources",
        "status": "installed",
        "owner": "adapter-launcher",
        "launcher_path": str(launcher),
        "receipt_path": str(receipt_file),
        "changed": launcher_changed or receipt_changed,
    }


def uninstall_launcher() -> dict[str, object]:
    """Remove only the launcher proven to be owned by the install receipt."""

    launcher = launcher_path()
    receipt_file = receipt_path()
    receipt = load_receipt()
    if receipt is None and not launcher.exists():
        return {"id": "remove-katana-launcher", "status": "uninstalled", "changed": False}
    if not _receipt_owns_launcher(receipt, launcher):
        raise InstallFailure(
            EXIT_INSTALL,
            "uninstall",
            "Install receipt does not prove ownership of the Katana launcher",
        )
    staged: list[tuple[Path, Path]] = []
    try:
        for path in (launcher, receipt_file):
            if not path.exists():
                continue
            backup = path.with_name(f".{path.name}.{secrets.token_hex(8)}.uninstall")
            os.replace(path, backup)
            staged.append((path, backup))
    except OSError as exc:
        for original, backup in reversed(staged):
            if backup.exists():
                os.replace(backup, original)
        if isinstance(exc, PermissionError):
            raise InstallFailure(
                EXIT_REQUIRES_RESTART,
                "launcher_locked",
                str(exc),
            ) from exc
        raise InstallFailure(EXIT_INSTALL, "uninstall", str(exc)) from exc
    for _original, backup in staged:
        backup.unlink(missing_ok=True)
    return {
        "id": "remove-katana-launcher",
        "status": "uninstalled",
        "changed": bool(staged),
    }
