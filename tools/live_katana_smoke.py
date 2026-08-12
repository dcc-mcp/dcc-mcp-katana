"""Exercise the production typed tool chain against an open real Katana host."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional


def run_cli(*args: str) -> Any:
    command = [
        "dcc-mcp-cli",
        "--gateway",
        "local",
        "--output",
        "json",
        "--non-interactive",
        *args,
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "Command failed: %s\nstdout=%s\nstderr=%s"
            % (" ".join(command), completed.stdout, completed.stderr)
        )
    return json.loads(completed.stdout)


def call(name: str, arguments: Optional[dict[str, Any]] = None) -> Any:
    return run_cli(
        "call",
        f"katana-nodegraph.{name}",
        "--dcc-type",
        "katana",
        "--json",
        json.dumps(arguments or {}, separators=(",", ":")),
        "--wait",
        "--wait-timeout-secs",
        "300",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> None:
    smoke_root_value = os.environ.get("DCC_MCP_KATANA_SMOKE_ROOT")
    if not smoke_root_value:
        raise RuntimeError("DCC_MCP_KATANA_SMOKE_ROOT must name an existing writable directory")
    smoke_root = Path(smoke_root_value).expanduser().resolve()
    if not smoke_root.is_dir():
        raise RuntimeError("DCC_MCP_KATANA_SMOKE_ROOT must name an existing directory")

    run_cli("wait-ready", "--dcc-type", "katana", "--timeout-secs", "60")
    run_cli("load-skill", "katana-nodegraph", "--dcc-type", "katana")

    suffix = str(int(time.time()))[-8:]
    primitive = f"DCCMCP_Primitive_{suffix}"
    merge = f"DCCMCP_Merge_{suffix}"
    project = smoke_root / f"dcc-mcp-katana-live-{suffix}.katana"

    call("get_status")
    call("inspect_nodegraph")
    call(
        "create_node",
        {"node_type": "PrimitiveCreate", "name": primitive, "position": [0, 0]},
    )
    call("create_node", {"node_type": "Merge", "name": merge, "position": [250, 0]})
    call(
        "set_parameter_value", {"node_name": primitive, "parameter_path": "type", "value": "sphere"}
    )
    call("add_port", {"node_name": primitive, "direction": "output", "port_name": "dcc_out"})
    call("add_port", {"node_name": merge, "direction": "input", "port_name": "dcc_in"})
    call(
        "connect_ports",
        {
            "source_node": primitive,
            "source_port": "dcc_out",
            "target_node": merge,
            "target_port": "dcc_in",
        },
    )
    call("set_timeline", {"in_time": 1, "out_time": 100, "current_time": 25})
    call("select_nodes", {"node_names": [primitive, merge], "mode": "replace"})
    call("get_parameter", {"node_name": primitive, "parameter_path": "type"})
    call("get_node", {"node_name": merge, "include_parameters": True})
    call("list_nodes", {"name_contains": "DCCMCP_", "limit": 100})
    call(
        "save_project",
        {"path": str(project), "overwrite": False, "create_parents": False},
    )

    if not project.is_file():
        raise RuntimeError("Katana project was not created")
    summary = {
        "typed_tools_exercised": 14,
        "nodes": [primitive, merge],
        "project": {
            "path": str(project),
            "bytes": project.stat().st_size,
            "sha256": sha256(project),
        },
    }
    if os.environ.get("DCC_MCP_KATANA_SMOKE_CLEANUP") == "1":
        call("delete_nodes", {"node_names": [primitive, merge], "confirm": True})
        summary["cleanup"] = True
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
