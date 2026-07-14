"""List nodes in the active Katana node graph."""

from dcc_mcp_core.skill import skill_entry, skill_success


@skill_entry
def main(**_kwargs):
    import NodegraphAPI  # Lazy import: requires Katana.

    nodes = [
        {"name": node.getName(), "type": node.getType()} for node in NodegraphAPI.GetAllNodes()
    ]
    return skill_success("Katana nodes listed.", nodes=nodes, node_count=len(nodes))


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
