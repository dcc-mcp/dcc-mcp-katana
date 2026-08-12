"""Remove one explicitly confirmed Katana node port."""

from dcc_mcp_core.skill import skill_entry

from dcc_mcp_katana.operations import remove_port
from dcc_mcp_katana.skill_support import invoke


@skill_entry
def main(**kwargs):
    return invoke("Katana port removed.", remove_port, **kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
