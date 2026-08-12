"""Bounded, typed operations implemented with Katana's official Python APIs."""

from __future__ import annotations

import hashlib
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

MAX_NODE_RESULTS = 1000
MAX_SELECTED_NODES = 100
MAX_DELETE_NODES = 100
MAX_PARAMETER_CHILDREN = 100
MAX_TEXT_LENGTH = 512
HASH_CHUNK_BYTES = 1024 * 1024


class KatanaOperationError(ValueError):
    """An expected, user-correctable operation error."""


def _nodegraph_api():
    import NodegraphAPI

    return NodegraphAPI


def _katana_file():
    import KatanaFile

    return KatanaFile


def _bounded_text(value: Any, field: str, *, maximum: int = MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str):
        raise KatanaOperationError(f"{field} must be a string")
    text = value.strip()
    if not text:
        raise KatanaOperationError(f"{field} must not be empty")
    if len(text) > maximum:
        raise KatanaOperationError(f"{field} must be at most {maximum} characters")
    if any(ord(character) < 32 for character in text):
        raise KatanaOperationError(f"{field} must not contain control characters")
    return text


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise KatanaOperationError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise KatanaOperationError(f"{field} must be finite")
    return number


def _bounded_integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise KatanaOperationError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise KatanaOperationError(f"{field} must be between {minimum} and {maximum}")
    return value


def _node_or_error(name: str):
    clean_name = _bounded_text(name, "node_name")
    node = _nodegraph_api().GetNode(clean_name)
    if node is None:
        raise KatanaOperationError(f"Node not found: {clean_name}")
    return node


def _port_or_error(node: Any, port_name: str, direction: str):
    clean_name = _bounded_text(port_name, f"{direction}_port", maximum=256)
    method = node.getOutputPort if direction == "output" else node.getInputPort
    port = method(clean_name)
    if port is None:
        raise KatanaOperationError(
            f"{direction.title()} port not found on {node.getName()}: {clean_name}"
        )
    return port


def _node_summary(node: Any) -> dict[str, Any]:
    parent = node.getParent() if hasattr(node, "getParent") else None
    return {
        "name": str(node.getName()),
        "type": str(node.getType()),
        "parent": str(parent.getName()) if parent is not None else None,
        "position": _position(node),
    }


def _position(node: Any) -> list[float]:
    api = _nodegraph_api()
    try:
        position = api.GetNodePosition(node)
    except Exception:
        return [0.0, 0.0]
    if not isinstance(position, (list, tuple)) or len(position) != 2:
        return [0.0, 0.0]
    return [float(position[0]), float(position[1])]


def _connection_summary(port: Any) -> list[dict[str, str]]:
    connections = []
    for connected in list(port.getConnectedPorts() or []):
        node = connected.getNode()
        connections.append({"node": str(node.getName()), "port": str(connected.getName())})
    return sorted(connections, key=lambda item: (item["node"], item["port"]))


def _port_summary(port: Any) -> dict[str, Any]:
    return {"name": str(port.getName()), "connections": _connection_summary(port)}


def _parameter_type(parameter: Any) -> str:
    method = getattr(parameter, "getType", None)
    if method is None:
        return type(parameter).__name__
    try:
        return str(method())
    except Exception:
        return type(parameter).__name__


def _parameter_value(parameter: Any, time: float) -> Any:
    try:
        value = parameter.getValue(time)
    except Exception as error:
        raise KatanaOperationError("Parameter does not expose a scalar value") from error
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        values = list(value)
        if len(values) > MAX_PARAMETER_CHILDREN:
            values = values[:MAX_PARAMETER_CHILDREN]
        if all(item is None or isinstance(item, (bool, int, float, str)) for item in values):
            return values
    return str(value)


def _parameter_children(parameter: Any, time: float) -> list[dict[str, Any]]:
    method = getattr(parameter, "getChildren", None)
    if method is None:
        return []
    children = list(method() or [])[:MAX_PARAMETER_CHILDREN]
    result = []
    for child in children:
        item = {"name": str(child.getName()), "type": _parameter_type(child)}
        try:
            item["value"] = _parameter_value(child, time)
        except KatanaOperationError:
            pass
        result.append(item)
    return result


def get_status() -> dict[str, Any]:
    api = _nodegraph_api()
    katana_file = _katana_file()
    nodes = list(api.GetAllNodes())
    node_types = Counter(str(node.getType()) for node in nodes)
    project_file = api.GetProjectFile() if hasattr(api, "GetProjectFile") else None
    return {
        "host": "Katana",
        "project_file": str(project_file) if project_file else None,
        "dirty": bool(katana_file.IsFileDirty()),
        "node_count": len(nodes),
        "node_types": dict(sorted(node_types.items())),
        "timeline": {
            "in": float(api.GetInTime()),
            "out": float(api.GetOutTime()),
            "current": float(api.GetCurrentTime()),
        },
    }


def inspect_nodegraph() -> dict[str, Any]:
    api = _nodegraph_api()
    root = api.GetRootNode()
    nodes = list(api.GetAllNodes())
    selected = list(api.GetAllSelectedNodes())
    viewed = api.GetViewNode()
    return {
        "root_node": str(root.getName()),
        "node_count": len(nodes),
        "selected_nodes": [str(node.getName()) for node in selected[:MAX_SELECTED_NODES]],
        "selected_count": len(selected),
        "selected_truncated": len(selected) > MAX_SELECTED_NODES,
        "viewed_node": str(viewed.getName()) if viewed else None,
    }


def list_nodes(
    *,
    node_type: Optional[str] = None,
    name_contains: Optional[str] = None,
    offset: int = 0,
    limit: int = 200,
) -> dict[str, Any]:
    if node_type is not None:
        node_type = _bounded_text(node_type, "node_type", maximum=128)
    if name_contains is not None:
        name_contains = _bounded_text(name_contains, "name_contains", maximum=128).casefold()
    offset = _bounded_integer(offset, "offset", 0, 1_000_000)
    limit = _bounded_integer(limit, "limit", 1, MAX_NODE_RESULTS)
    nodes = []
    for node in _nodegraph_api().GetAllNodes():
        if node_type is not None and str(node.getType()) != node_type:
            continue
        if name_contains is not None and name_contains not in str(node.getName()).casefold():
            continue
        nodes.append(node)
    nodes.sort(key=lambda item: str(item.getName()).casefold())
    page = nodes[offset : offset + limit]
    return {
        "nodes": [_node_summary(node) for node in page],
        "total": len(nodes),
        "offset": offset,
        "limit": limit,
        "truncated": offset + len(page) < len(nodes),
    }


def get_node(
    *, node_name: str, include_parameters: bool = False, time: Optional[float] = None
) -> dict[str, Any]:
    if not isinstance(include_parameters, bool):
        raise KatanaOperationError("include_parameters must be a boolean")
    api = _nodegraph_api()
    node = _node_or_error(node_name)
    sample_time = float(api.GetCurrentTime()) if time is None else _finite_number(time, "time")
    result = _node_summary(node)
    result["input_ports"] = [_port_summary(port) for port in list(node.getInputPorts())]
    result["output_ports"] = [_port_summary(port) for port in list(node.getOutputPorts())]
    if include_parameters:
        result["parameters"] = _parameter_children(node.getParameters(), sample_time)
        result["parameters_truncated"] = (
            len(list(node.getParameters().getChildren() or [])) > MAX_PARAMETER_CHILDREN
        )
        result["parameter_time"] = sample_time
    return result


def create_node(
    *,
    node_type: str,
    parent_name: Optional[str] = None,
    name: Optional[str] = None,
    position: Optional[Sequence[float]] = None,
) -> dict[str, Any]:
    api = _nodegraph_api()
    clean_type = _bounded_text(node_type, "node_type", maximum=128)
    parent = api.GetRootNode() if parent_name is None else _node_or_error(parent_name)
    node = api.CreateNode(clean_type, parent)
    if node is None:
        raise KatanaOperationError(f"Katana could not create node type: {clean_type}")
    try:
        if name is not None:
            node.setName(_bounded_text(name, "name", maximum=128))
        if position is not None:
            if not isinstance(position, (list, tuple)) or len(position) != 2:
                raise KatanaOperationError("position must contain exactly two numbers")
            api.SetNodePosition(
                node,
                (
                    _finite_number(position[0], "position[0]"),
                    _finite_number(position[1], "position[1]"),
                ),
            )
    except Exception:
        api.DeleteNode(node)
        raise
    return {"node": _node_summary(node)}


def rename_node(*, node_name: str, new_name: str) -> dict[str, Any]:
    node = _node_or_error(node_name)
    root = _nodegraph_api().GetRootNode()
    if node is root:
        raise KatanaOperationError("The root node cannot be renamed")
    previous = str(node.getName())
    node.setName(_bounded_text(new_name, "new_name", maximum=128))
    return {"previous_name": previous, "node": _node_summary(node)}


def delete_nodes(*, node_names: Sequence[str], confirm: bool = False) -> dict[str, Any]:
    if confirm is not True:
        raise KatanaOperationError("confirm must be true to delete nodes")
    if not isinstance(node_names, list) or not node_names:
        raise KatanaOperationError("node_names must be a non-empty array")
    if len(node_names) > MAX_DELETE_NODES:
        raise KatanaOperationError(f"node_names is limited to {MAX_DELETE_NODES} entries")
    api = _nodegraph_api()
    root = api.GetRootNode()
    nodes = []
    seen = set()
    for name in node_names:
        node = _node_or_error(name)
        if node is root:
            raise KatanaOperationError("The root node cannot be deleted")
        canonical_name = str(node.getName())
        if canonical_name not in seen:
            nodes.append(node)
            seen.add(canonical_name)
    deleted = [str(node.getName()) for node in nodes]
    for node in nodes:
        api.DeleteNode(node)
    return {"deleted_nodes": deleted, "deleted_count": len(deleted)}


def set_node_position(*, node_name: str, x: float, y: float) -> dict[str, Any]:
    api = _nodegraph_api()
    node = _node_or_error(node_name)
    position = (_finite_number(x, "x"), _finite_number(y, "y"))
    api.SetNodePosition(node, position)
    return {"node": _node_summary(node)}


def select_nodes(*, node_names: Sequence[str], mode: str = "replace") -> dict[str, Any]:
    if not isinstance(node_names, list):
        raise KatanaOperationError("node_names must be an array")
    if len(node_names) > MAX_SELECTED_NODES:
        raise KatanaOperationError(f"node_names is limited to {MAX_SELECTED_NODES} entries")
    clean_mode = _bounded_text(mode, "mode", maximum=16).lower()
    if clean_mode not in {"replace", "add", "remove"}:
        raise KatanaOperationError("mode must be replace, add, or remove")
    api = _nodegraph_api()
    nodes = [_node_or_error(name) for name in node_names]
    if clean_mode == "replace":
        for selected in list(api.GetAllSelectedNodes()):
            api.SetNodeSelected(selected, False)
    selected_value = clean_mode != "remove"
    for node in nodes:
        api.SetNodeSelected(node, selected_value)
    selected = list(api.GetAllSelectedNodes())
    return {
        "selected_nodes": [str(node.getName()) for node in selected[:MAX_SELECTED_NODES]],
        "selected_count": len(selected),
        "selected_truncated": len(selected) > MAX_SELECTED_NODES,
    }


def get_parameter(
    *, node_name: str, parameter_path: str, time: Optional[float] = None
) -> dict[str, Any]:
    api = _nodegraph_api()
    node = _node_or_error(node_name)
    clean_path = _bounded_text(parameter_path, "parameter_path")
    parameter = node.getParameter(clean_path)
    if parameter is None:
        raise KatanaOperationError(f"Parameter not found on {node.getName()}: {clean_path}")
    sample_time = float(api.GetCurrentTime()) if time is None else _finite_number(time, "time")
    return {
        "node_name": str(node.getName()),
        "parameter_path": clean_path,
        "parameter_type": _parameter_type(parameter),
        "value": _parameter_value(parameter, sample_time),
        "time": sample_time,
    }


def set_parameter_value(
    *, node_name: str, parameter_path: str, value: Any, time: Optional[float] = None
) -> dict[str, Any]:
    if value is None or not isinstance(value, (bool, int, float, str)):
        raise KatanaOperationError("value must be a JSON string, boolean, or finite number")
    if isinstance(value, float) and not math.isfinite(value):
        raise KatanaOperationError("value must be finite")
    if isinstance(value, str) and len(value) > 64 * 1024:
        raise KatanaOperationError("string values are limited to 65536 characters")
    api = _nodegraph_api()
    node = _node_or_error(node_name)
    clean_path = _bounded_text(parameter_path, "parameter_path")
    parameter = node.getParameter(clean_path)
    if parameter is None:
        raise KatanaOperationError(f"Parameter not found on {node.getName()}: {clean_path}")
    sample_time = float(api.GetCurrentTime()) if time is None else _finite_number(time, "time")
    parameter.setValue(value, sample_time)
    return get_parameter(node_name=str(node.getName()), parameter_path=clean_path, time=sample_time)


def add_port(*, node_name: str, direction: str, port_name: str) -> dict[str, Any]:
    node = _node_or_error(node_name)
    clean_direction = _bounded_text(direction, "direction", maximum=16).lower()
    if clean_direction not in {"input", "output"}:
        raise KatanaOperationError("direction must be input or output")
    clean_name = _bounded_text(port_name, "port_name", maximum=256)
    getter = node.getInputPort if clean_direction == "input" else node.getOutputPort
    existing = getter(clean_name)
    if existing is not None:
        return {
            "node_name": str(node.getName()),
            "direction": clean_direction,
            "port": _port_summary(existing),
            "changed": False,
        }
    creator = node.addInputPort if clean_direction == "input" else node.addOutputPort
    port = creator(clean_name)
    if port is None:
        port = getter(clean_name)
    if port is None:
        raise RuntimeError("Katana did not create the requested port")
    return {
        "node_name": str(node.getName()),
        "direction": clean_direction,
        "port": _port_summary(port),
        "changed": True,
    }


def remove_port(
    *, node_name: str, direction: str, port_name: str, confirm: bool = False
) -> dict[str, Any]:
    if confirm is not True:
        raise KatanaOperationError("confirm must be true to remove a port")
    node = _node_or_error(node_name)
    if node is _nodegraph_api().GetRootNode():
        raise KatanaOperationError("Ports cannot be removed from the root node")
    clean_direction = _bounded_text(direction, "direction", maximum=16).lower()
    if clean_direction not in {"input", "output"}:
        raise KatanaOperationError("direction must be input or output")
    port = _port_or_error(node, port_name, clean_direction)
    connected_count = len(list(port.getConnectedPorts() or []))
    remover = node.removeInputPort if clean_direction == "input" else node.removeOutputPort
    remover(port.getName())
    return {
        "node_name": str(node.getName()),
        "direction": clean_direction,
        "port_name": str(port.getName()),
        "disconnected_count": connected_count,
        "removed": True,
    }


def connect_ports(
    *, source_node: str, source_port: str, target_node: str, target_port: str
) -> dict[str, Any]:
    source = _node_or_error(source_node)
    target = _node_or_error(target_node)
    output = _port_or_error(source, source_port, "output")
    input_port = _port_or_error(target, target_port, "input")
    if input_port in list(output.getConnectedPorts() or []):
        return {"connected": True, "changed": False}
    output.connect(input_port)
    return {"connected": True, "changed": True}


def disconnect_ports(
    *, source_node: str, source_port: str, target_node: str, target_port: str
) -> dict[str, Any]:
    source = _node_or_error(source_node)
    target = _node_or_error(target_node)
    output = _port_or_error(source, source_port, "output")
    input_port = _port_or_error(target, target_port, "input")
    if input_port not in list(output.getConnectedPorts() or []):
        return {"connected": False, "changed": False}
    output.disconnect(input_port)
    return {"connected": False, "changed": True}


def set_timeline(
    *,
    in_time: Optional[float] = None,
    out_time: Optional[float] = None,
    current_time: Optional[float] = None,
) -> dict[str, Any]:
    if in_time is None and out_time is None and current_time is None:
        raise KatanaOperationError("At least one timeline value is required")
    api = _nodegraph_api()
    new_in = float(api.GetInTime()) if in_time is None else _finite_number(in_time, "in_time")
    new_out = float(api.GetOutTime()) if out_time is None else _finite_number(out_time, "out_time")
    new_current = (
        float(api.GetCurrentTime())
        if current_time is None
        else _finite_number(current_time, "current_time")
    )
    if new_in > new_out:
        raise KatanaOperationError("in_time must be less than or equal to out_time")
    if new_current < new_in or new_current > new_out:
        raise KatanaOperationError("current_time must be within the in/out range")
    api.SetInTime(new_in)
    api.SetOutTime(new_out)
    api.SetCurrentTime(new_current)
    return {"timeline": {"in": new_in, "out": new_out, "current": new_current}}


def _allowed_roots() -> list[Path]:
    configured = os.environ.get("DCC_MCP_KATANA_ALLOWED_ROOTS", "")
    values = [value for value in configured.split(os.pathsep) if value.strip()]
    if not values:
        values = [str(Path.home())]
    roots = []
    for value in values:
        root = Path(value).expanduser()
        if not root.is_absolute():
            raise KatanaOperationError("DCC_MCP_KATANA_ALLOWED_ROOTS must contain absolute paths")
        roots.append(root.resolve(strict=False))
    return roots


def _safe_project_path(path: str) -> Path:
    target = Path(_bounded_text(path, "path", maximum=4096)).expanduser()
    if not target.is_absolute():
        raise KatanaOperationError("path must be absolute")
    target = target.resolve(strict=False)
    if target.suffix.lower() != ".katana":
        raise KatanaOperationError("path must end with .katana")
    if not any(target == root or root in target.parents for root in _allowed_roots()):
        raise KatanaOperationError("path is outside DCC_MCP_KATANA_ALLOWED_ROOTS")
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def save_project(
    *, path: str, overwrite: bool = False, create_parents: bool = False
) -> dict[str, Any]:
    if not isinstance(overwrite, bool) or not isinstance(create_parents, bool):
        raise KatanaOperationError("overwrite and create_parents must be booleans")
    target = _safe_project_path(path)
    if target.exists() and not overwrite:
        raise KatanaOperationError("target already exists; set overwrite=true to replace it")
    if not target.parent.exists():
        if not create_parents:
            raise KatanaOperationError("parent directory does not exist")
        target.parent.mkdir(parents=True, exist_ok=True)
    if not target.parent.is_dir():
        raise KatanaOperationError("parent path is not a directory")
    _katana_file().Save(str(target))
    if not target.is_file():
        raise RuntimeError("Katana reported success but the project file was not created")
    return {
        "path": str(target),
        "bytes": target.stat().st_size,
        "sha256": _sha256(target),
    }


def node_names(nodes: Iterable[Any]) -> list[str]:
    """Return stable node names; kept public for host smoke tests."""

    return [str(node.getName()) for node in nodes]
