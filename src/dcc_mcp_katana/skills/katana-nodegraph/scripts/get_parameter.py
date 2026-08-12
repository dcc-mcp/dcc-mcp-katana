"""Read a scalar Katana node parameter."""

from dcc_mcp_core.skill import skill_entry

from dcc_mcp_katana.operations import get_parameter
from dcc_mcp_katana.skill_support import invoke


@skill_entry
def main(**kwargs):
    return invoke("Katana parameter returned.", get_parameter, **kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
