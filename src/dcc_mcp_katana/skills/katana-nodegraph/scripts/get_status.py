"""Return bounded Katana project and timeline status."""

from dcc_mcp_core.skill import skill_entry

from dcc_mcp_katana.operations import get_status
from dcc_mcp_katana.skill_support import invoke


@skill_entry
def main(**_kwargs):
    return invoke("Katana status returned.", get_status)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
