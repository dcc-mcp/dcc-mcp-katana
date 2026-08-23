"""Fail-safe diagnostics for the Katana startup entry point."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def bootstrap_error_path() -> Path:
    configured = os.environ.get("DCC_MCP_KATANA_BOOTSTRAP_ERROR_LOG")
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    return Path.home() / ".dcc-mcp" / "logs" / "katana-bootstrap-errors.jsonl"


def _append_record(record: dict[str, Any]) -> None:
    path = bootstrap_error_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def initialize_with_capture(initialize: Callable[[], None]) -> None:
    """Run the real startup hook, preserving its exception after local capture."""

    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        initialize()
    except BaseException as exc:
        try:
            _append_record(
                {
                    "timestamp": timestamp,
                    "stage": "initialize",
                    "success": False,
                    "exception_type": type(exc).__name__,
                    "reason": str(exc),
                }
            )
        except OSError:
            pass
        raise
    try:
        _append_record({"timestamp": timestamp, "stage": "initialize", "success": True})
    except OSError:
        pass


def bootstrap_error_summary() -> dict[str, Any]:
    path = bootstrap_error_path()
    if not path.is_file():
        return {"path": str(path), "last": None, "records_read": 0, "truncated": False}
    try:
        payload = path.read_bytes()
    except OSError as exc:
        return {
            "path": str(path),
            "last": {"success": False, "exception_type": type(exc).__name__, "reason": str(exc)},
            "records_read": 0,
            "truncated": False,
        }
    limit = 256 * 1024
    truncated = len(payload) > limit
    if truncated:
        payload = payload[-limit:]
        payload = payload.split(b"\n", 1)[-1]
    records = []
    for line in payload.splitlines():
        try:
            record = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(record, dict):
            records.append(record)
    return {
        "path": str(path),
        "last": records[-1] if records else None,
        "records_read": len(records),
        "truncated": truncated,
    }
