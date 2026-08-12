"""Move a Katana node in the node graph."""

from dcc_mcp_core.skill import skill_entry

from dcc_mcp_katana.operations import set_node_position
from dcc_mcp_katana.skill_support import invoke


@skill_entry
def main(**kwargs):
    return invoke("Katana node position updated.", set_node_position, **kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
