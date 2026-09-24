"""Thin, replaceable Install SOP contract for the Katana adapter."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

# Last-resort value for the report's own ``schema_version`` field, used only when Core's
# schema document cannot be read at all. See ``report_schema_version()``.
#
# This is deliberately NOT Core's ``INSTALL_SOP_SCHEMA_VERSION``. That constant is the revision
# of the published schema *artifact* (``-vN``); Core documents it as separate from the report
# field, which stays at 1 because v2 only adds the optional ``catalog`` object. The two values
# coincided at 1 through Core 0.20.33, which is why copying the constant into the report looked
# correct right up until 0.20.34 bumped the artifact revision to 2.
FALLBACK_REPORT_SCHEMA_VERSION = 1
# The install receipt is its own document, separate from the Install SOP report; it owns its
# revision rather than following the artifact Core publishes.
RECEIPT_SCHEMA_VERSION = 1

try:
    from dcc_mcp_core.deployment import load_install_sop_schema
except ImportError:  # pragma: no cover - Core too old to ship the published schema loader.
    load_install_sop_schema = None

try:
    import dcc_mcp_core as _core

    EXIT_OK = _core.INSTALL_EXIT_OK
    EXIT_PREFLIGHT = _core.INSTALL_EXIT_PREFLIGHT
    EXIT_ACQUIRE = _core.INSTALL_EXIT_ACQUIRE
    EXIT_INSTALL = _core.INSTALL_EXIT_INSTALL
    EXIT_VERIFY = _core.INSTALL_EXIT_VERIFY
    EXIT_REQUIRES_RESTART = _core.INSTALL_EXIT_REQUIRES_RESTART
except AttributeError:  # Compatibility until the Core #2252 exports reach the minimum release.
    EXIT_OK, EXIT_PREFLIGHT, EXIT_ACQUIRE = 0, 10, 20
    EXIT_INSTALL, EXIT_VERIFY, EXIT_REQUIRES_RESTART = 30, 40, 50

MIN_CORE_VERSION = "0.19.45"
MIN_KATANA_MAJOR = 6
LIFECYCLE_VERBS = {"install", "status", "verify", "uninstall", "upgrade"}


def report_schema_version() -> int:
    """Return the ``schema_version`` value every emitted report must carry.

    Core enforces this value as the ``const`` of the ``schema_version`` property in the schema
    document it ships, so that document is the authoritative source -- emitting anything else
    produces reports Core's own validator rejects.

    Core's exported ``INSTALL_SOP_SCHEMA_VERSION`` is deliberately NOT used. It is the revision
    of the published schema *artifact* (``-vN``), a separate quantity from the report's own
    field; the two merely happened to agree while both were 1. Populating the report from that
    constant is the defect this function exists to avoid.

    Reading the document touches the disk and is verified by Core with a SHA-256 digest, so a
    partially installed, tampered, or otherwise unhealthy Core can make the read fail. It falls
    back to ``FALLBACK_REPORT_SCHEMA_VERSION`` rather than propagating, because the installer's
    job is to keep emitting a preflight report precisely when the environment is broken.
    """
    if load_install_sop_schema is None:
        return FALLBACK_REPORT_SCHEMA_VERSION
    try:
        document = load_install_sop_schema()
        declared = document["properties"]["schema_version"]["const"]
    except Exception:
        # KeyError/TypeError (document shape changed) and the RuntimeError/OSError/ValueError
        # Core raises on a missing, unreadable, or tampered document all degrade to the
        # fallback for the same reason.
        return FALLBACK_REPORT_SCHEMA_VERSION
    if isinstance(declared, bool) or not isinstance(declared, int):
        return FALLBACK_REPORT_SCHEMA_VERSION
    return declared


class InstallFailure(ValueError):
    """A lifecycle stage failed with a stable Install SOP exit code."""

    def __init__(self, exit_code: int, stage: str, reason: str):
        super().__init__(reason)
        self.exit_code = exit_code
        self.stage = stage
        self.reason = reason


def version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for item in value.split("."):
        digits = "".join(character for character in item if character.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def runtime_core_version() -> str:
    try:
        return version("dcc-mcp-core")
    except PackageNotFoundError:
        return "unavailable"


def empty_verify() -> dict[str, object]:
    return {
        "directly_usable": False,
        "failure_stage": None,
        "failure_reason": None,
    }
