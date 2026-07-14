"""Inspect the active Katana node graph."""

from dcc_mcp_core.skill import skill_entry, skill_success


@skill_entry
def main(**_kwargs):
    import NodegraphAPI  # Lazy import: requires Katana.

    root = NodegraphAPI.GetRootNode()
    selected = NodegraphAPI.GetAllSelectedNodes()
    viewed = NodegraphAPI.GetViewNode()
    return skill_success(
        "Katana node graph inspected.",
        root_node=root.getName(),
        node_count=len(NodegraphAPI.GetAllNodes()),
        selected_nodes=[node.getName() for node in selected],
        viewed_node=viewed.getName() if viewed else None,
    )


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
