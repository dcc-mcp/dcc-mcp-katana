"""Save the active Katana project."""

from pathlib import Path

from dcc_mcp_core.skill import skill_entry, skill_error, skill_success


@skill_entry
def main(path: str, **_kwargs):
    target = Path(path).expanduser()
    if not target.is_absolute():
        return skill_error("path must be absolute")
    if target.suffix.lower() != ".katana":
        return skill_error("path must end with .katana")

    import KatanaFile  # Lazy import: requires Katana.

    target.parent.mkdir(parents=True, exist_ok=True)
    KatanaFile.Save(str(target))
    return skill_success("Katana project saved.", path=str(target))


if __name__ == "__main__":
    from dcc_mcp_core.skill import run_main

    run_main(main)
