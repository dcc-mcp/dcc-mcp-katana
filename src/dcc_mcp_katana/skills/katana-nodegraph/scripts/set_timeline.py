"""Set a bounded Katana timeline range and current frame."""

from dcc_mcp_core.skill import skill_entry

from dcc_mcp_katana.operations import set_timeline
from dcc_mcp_katana.skill_support import invoke


@skill_entry
def main(**kwargs):
    return invoke("Katana timeline updated.", set_timeline, **kwargs)


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
