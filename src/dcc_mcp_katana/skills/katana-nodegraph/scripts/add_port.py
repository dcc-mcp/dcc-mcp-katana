"""Add one typed input or output port to a Katana node."""

from dcc_mcp_core.skill import skill_entry

from dcc_mcp_katana.operations import add_port
from dcc_mcp_katana.skill_support import invoke


@skill_entry
def main(**kwargs):
    return invoke("Katana port added.", add_port, **kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
