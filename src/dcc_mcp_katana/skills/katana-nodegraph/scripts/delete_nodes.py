"""Delete explicitly confirmed Katana nodes."""

from dcc_mcp_core.skill import skill_entry

from dcc_mcp_katana.operations import delete_nodes
from dcc_mcp_katana.skill_support import invoke


@skill_entry
def main(**kwargs):
    return invoke("Katana nodes deleted.", delete_nodes, **kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
