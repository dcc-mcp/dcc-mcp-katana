from __future__ import annotations

import hashlib
import sys
from types import SimpleNamespace

import pytest

from dcc_mcp_katana import operations


class FakeParameter:
    def __init__(self, name, value=None, parameter_type="number", children=None):
        self.name = name
        self.value = value
        self.parameter_type = parameter_type
        self.children = list(children or [])

    def getName(self):
        return self.name

    def getType(self):
        return self.parameter_type

    def getChildren(self):
        return list(self.children)

    def getValue(self, _time):
        if self.children:
            raise TypeError("group")
        return self.value

    def setValue(self, value, _time):
        self.value = value


class FakePort:
    def __init__(self, node, name):
        self.node = node
        self.name = name
        self.connections = []

    def getName(self):
        return self.name

    def getNode(self):
        return self.node

    def getConnectedPorts(self):
        return list(self.connections)

    def connect(self, other):
        if other not in self.connections:
            self.connections.append(other)
        if self not in other.connections:
            other.connections.append(self)

    def disconnect(self, other):
        if other in self.connections:
            self.connections.remove(other)
        if self in other.connections:
            other.connections.remove(self)


class FakeNode:
    def __init__(self, name, node_type, parent=None):
        self.name = name
        self.node_type = node_type
        self.parent = parent
        self.inputs = [FakePort(self, "in")]
        self.outputs = [FakePort(self, "out")]
        self.parameters = {
            "value": FakeParameter("value", 1.0),
            "label": FakeParameter("label", name, "string"),
        }
        self.parameter_root = FakeParameter(
            "root", parameter_type="group", children=list(self.parameters.values())
        )

    def getName(self):
        return self.name

    def setName(self, name):
        self.name = name

    def getType(self):
        return self.node_type

    def getParent(self):
        return self.parent

    def getInputPorts(self):
        return list(self.inputs)

    def getOutputPorts(self):
        return list(self.outputs)

    def getInputPort(self, name):
        return next((port for port in self.inputs if port.name == name), None)

    def getOutputPort(self, name):
        return next((port for port in self.outputs if port.name == name), None)

    def addInputPort(self, name):
        port = FakePort(self, name)
        self.inputs.append(port)
        return port

    def addOutputPort(self, name):
        port = FakePort(self, name)
        self.outputs.append(port)
        return port

    def removeInputPort(self, name):
        port = self.getInputPort(name)
        for connected in list(port.connections):
            port.disconnect(connected)
        self.inputs.remove(port)

    def removeOutputPort(self, name):
        port = self.getOutputPort(name)
        for connected in list(port.connections):
            port.disconnect(connected)
        self.outputs.remove(port)

    def getParameters(self):
        return self.parameter_root

    def getParameter(self, path):
        return self.parameters.get(path)


@pytest.fixture
def fake_host(monkeypatch):
    root = FakeNode("rootNode", "Root")
    primitive = FakeNode("PrimitiveCreate", "PrimitiveCreate", root)
    render = FakeNode("Render", "Render", root)
    state = {
        "nodes": [root, primitive, render],
        "selected": [primitive],
        "viewed": render,
        "positions": {root: (0.0, 0.0), primitive: (10.0, 20.0), render: (30.0, 40.0)},
        "in": 1.0,
        "out": 100.0,
        "current": 1.0,
    }

    def get_node(name):
        return next((node for node in state["nodes"] if node.name == name), None)

    def create_node(node_type, parent):
        node = FakeNode(f"{node_type}{len(state['nodes'])}", node_type, parent)
        state["nodes"].append(node)
        state["positions"][node] = (0.0, 0.0)
        return node

    def delete_node(node):
        state["nodes"].remove(node)
        state["selected"] = [item for item in state["selected"] if item is not node]
        state["positions"].pop(node, None)

    def set_selected(node, selected):
        if selected and node not in state["selected"]:
            state["selected"].append(node)
        if not selected and node in state["selected"]:
            state["selected"].remove(node)

    api = SimpleNamespace(
        GetRootNode=lambda: root,
        GetNode=get_node,
        GetAllNodes=lambda: list(state["nodes"]),
        GetAllSelectedNodes=lambda: list(state["selected"]),
        GetViewNode=lambda: state["viewed"],
        GetNodePosition=lambda node: state["positions"][node],
        SetNodePosition=lambda node, position: state["positions"].__setitem__(node, position),
        SetNodeSelected=set_selected,
        CreateNode=create_node,
        DeleteNode=delete_node,
        GetProjectFile=lambda: "/show/lookdev.katana",
        GetInTime=lambda: state["in"],
        SetInTime=lambda value: state.__setitem__("in", value),
        GetOutTime=lambda: state["out"],
        SetOutTime=lambda value: state.__setitem__("out", value),
        GetCurrentTime=lambda: state["current"],
        SetCurrentTime=lambda value: state.__setitem__("current", value),
    )

    class FakeKatanaFile:
        @staticmethod
        def IsFileDirty():
            return True

        @staticmethod
        def Save(path):
            with open(path, "wb") as stream:
                stream.write(b"katana-test-project")

    monkeypatch.setitem(sys.modules, "NodegraphAPI", api)
    monkeypatch.setitem(sys.modules, "KatanaFile", FakeKatanaFile)
    return state


def test_status_inspect_and_bounded_listing(fake_host):
    status = operations.get_status()
    assert status["dirty"] is True
    assert status["node_count"] == 3
    assert status["node_types"] == {"PrimitiveCreate": 1, "Render": 1, "Root": 1}

    inspected = operations.inspect_nodegraph()
    assert inspected["root_node"] == "rootNode"
    assert inspected["selected_nodes"] == ["PrimitiveCreate"]
    assert inspected["viewed_node"] == "Render"

    listed = operations.list_nodes(name_contains="r", offset=1, limit=1)
    assert listed["total"] == 3
    assert listed["nodes"][0]["name"] == "Render"
    assert listed["truncated"] is True


def test_node_create_rename_position_selection_and_delete(fake_host):
    created = operations.create_node(node_type="Merge", name="MergeBeauty", position=[125, -40])[
        "node"
    ]
    assert created["name"] == "MergeBeauty"
    assert created["position"] == [125.0, -40.0]

    renamed = operations.rename_node(node_name="MergeBeauty", new_name="MergeFinal")
    assert renamed["previous_name"] == "MergeBeauty"
    operations.set_node_position(node_name="MergeFinal", x=200, y=50)
    assert operations.get_node(node_name="MergeFinal")["position"] == [200.0, 50.0]

    selection = operations.select_nodes(node_names=["MergeFinal"], mode="replace")
    assert selection["selected_nodes"] == ["MergeFinal"]
    deleted = operations.delete_nodes(node_names=["MergeFinal"], confirm=True)
    assert deleted == {"deleted_nodes": ["MergeFinal"], "deleted_count": 1}


def test_parameter_and_port_operations(fake_host):
    initial = operations.get_parameter(node_name="PrimitiveCreate", parameter_path="value")
    assert initial["value"] == 1.0
    updated = operations.set_parameter_value(
        node_name="PrimitiveCreate", parameter_path="value", value=2.5, time=10
    )
    assert updated["value"] == 2.5
    node = operations.get_node(node_name="PrimitiveCreate", include_parameters=True)
    assert {item["name"] for item in node["parameters"]} == {"label", "value"}

    added_output = operations.add_port(
        node_name="PrimitiveCreate", direction="output", port_name="beauty"
    )
    added_input = operations.add_port(node_name="Render", direction="input", port_name="beauty")
    assert added_output["changed"] is True
    assert added_input["changed"] is True
    assert (
        operations.add_port(node_name="Render", direction="input", port_name="beauty")["changed"]
        is False
    )

    connected = operations.connect_ports(
        source_node="PrimitiveCreate",
        source_port="beauty",
        target_node="Render",
        target_port="beauty",
    )
    assert connected == {"connected": True, "changed": True}
    assert operations.connect_ports(
        source_node="PrimitiveCreate",
        source_port="beauty",
        target_node="Render",
        target_port="beauty",
    ) == {"connected": True, "changed": False}
    assert operations.disconnect_ports(
        source_node="PrimitiveCreate",
        source_port="beauty",
        target_node="Render",
        target_port="beauty",
    ) == {"connected": False, "changed": True}
    removed = operations.remove_port(
        node_name="Render", direction="input", port_name="beauty", confirm=True
    )
    assert removed["removed"] is True


def test_timeline_validation_and_update(fake_host):
    result = operations.set_timeline(in_time=10, out_time=80, current_time=25)
    assert result["timeline"] == {"in": 10.0, "out": 80.0, "current": 25.0}
    with pytest.raises(operations.KatanaOperationError, match="within"):
        operations.set_timeline(current_time=100)


def test_save_project_is_allowlisted_and_verified(fake_host, monkeypatch, tmp_path):
    allowed = tmp_path / "projects"
    allowed.mkdir()
    monkeypatch.setenv("DCC_MCP_KATANA_ALLOWED_ROOTS", str(allowed))
    target = allowed / "shot.katana"
    result = operations.save_project(path=str(target))
    assert result["bytes"] == len(b"katana-test-project")
    assert result["sha256"] == hashlib.sha256(b"katana-test-project").hexdigest().upper()
    with pytest.raises(operations.KatanaOperationError, match="already exists"):
        operations.save_project(path=str(target))
    with pytest.raises(operations.KatanaOperationError, match="outside"):
        operations.save_project(path=str(tmp_path / "outside.katana"))


@pytest.mark.parametrize(
    ("callback", "match"),
    [
        (lambda: operations.delete_nodes(node_names=["rootNode"], confirm=True), "root"),
        (lambda: operations.delete_nodes(node_names=["Render"], confirm=False), "confirm"),
        (
            lambda: operations.set_parameter_value(
                node_name="Render", parameter_path="missing", value=1
            ),
            "Parameter not found",
        ),
        (lambda: operations.create_node(node_type="Merge", position=[1]), "exactly two"),
    ],
)
def test_expected_operation_errors(fake_host, callback, match):
    with pytest.raises(operations.KatanaOperationError, match=match):
        callback()
