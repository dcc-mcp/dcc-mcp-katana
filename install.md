# Install DCC-MCP for Katana

Canonical raw runbook: <https://raw.githubusercontent.com/dcc-mcp/dcc-mcp-katana/main/install.md>

## Requirements

- Foundry Katana 6.0 or newer.
- Python 3.9 or newer in the environment that loads the adapter.
- `dcc-mcp-core` 0.19.45 or newer.
- `dcc-mcp-katana` installed in that same Python environment.

The installer is supported on Windows, Linux, and macOS. The selected Katana build must also
be supported on that platform by Foundry. No UI automation is required.

## Supported versions

The preflight reads the real Katana and target-Python versions before changing files. Katana
6.0 or newer is accepted. Python 3.9 through 3.12 are covered by the repository CI.
Use `--dcc-path <katanaBin>` and `--python <python>` when automatic discovery is ambiguous.

## Agent quick path

Install the Python package in Katana's environment, inspect the plan, then apply it:

```bash
python -m pip install dcc-mcp-katana
dcc-mcp-katana install --dry-run --json
dcc-mcp-katana install --yes --json
dcc-mcp-katana status --json
```

The apply step creates an adapter-owned launcher under `.dcc-mcp/launchers/` and writes the
receipt `.dcc-mcp/receipts/katana.json`. It does not edit shell profiles or registry keys. The
launcher preserves the `KATANA_RESOURCES` value supplied by the studio or user and appends the
packaged resource directory for that Katana process.

Follow the returned `next_steps[].command` to launch Katana. That command is the persistent,
machine-executable host-enablement step.

## Manual path

If command discovery is unavailable, invoke the module with the target Python and explicit
host path:

```bash
python -m dcc_mcp_katana.cli install --dry-run --json --dcc-path /path/to/katanaBin --python /path/to/python
python -m dcc_mcp_katana.cli install --yes --json --dcc-path /path/to/katanaBin --python /path/to/python
```

Do not replace an existing studio `KATANA_RESOURCES` value. `dcc-mcp-katana resource-path`
prints the package resource only for auditing older manual setups; the owned launcher is the
recommended persistent integration.

## Verify

Start Katana using the launcher from the install result, then run:

```bash
dcc-mcp-katana doctor --json
dcc-mcp-katana verify --json
dcc-mcp-cli wait-ready --dcc-type katana
```

`verify` checks the receipt and launcher digest, imports the adapter in the recorded target
interpreter, waits for shared Core dispatch readiness, and calls the typed Katana `get_status`
probe. Success requires `verify.directly_usable` to be `true`; file presence alone is not
success.

## Upgrade

Upgrade the package in the recorded target environment, review the plan, and atomically refresh
the launcher and receipt:

```bash
python -m pip install --upgrade dcc-mcp-katana
dcc-mcp-katana upgrade --dry-run --json
dcc-mcp-katana upgrade --yes --json
dcc-mcp-katana verify --json
```

A stale adapter version stamp appears as `installation_state: "upgrade"`. A failed write restores
the prior launcher rather than removing the previous working integration.

## Uninstall

```bash
dcc-mcp-katana uninstall --dry-run --json
dcc-mcp-katana uninstall --yes --json
python -m pip uninstall dcc-mcp-katana
```

Uninstall consumes the receipt and removes only the launcher whose ownership it proves. It
fails closed instead of deleting an unknown file at the same path.

## Troubleshooting

- **Katana was not found (exit 10):** pass the `katanaBin` executable with `--dcc-path`.
- **Target Python or Core is unsupported (exit 10):** pass Katana's Python with `--python`, then
  install compatible `dcc-mcp-core` and `dcc-mcp-katana` distributions there.
- **State is `partial` or `repair`:** preserve the receipt and run
  `dcc-mcp-katana install --yes --json` to converge owned files. An unowned launcher must be
  moved or reviewed by its owner first.
- **Bootstrap failed:** inspect the bounded summary in `dcc-mcp-katana doctor --json` and the
  local `~/.dcc-mcp/logs/katana-bootstrap-errors.jsonl` record.
- **Verify reaches readiness and times out (exit 40):** launch Katana using the returned launcher,
  then inspect the Core registry row, host RPC endpoint, and adapter logs. Automated CI uses a
  contract-compatible host; a real Katana session is still required for live-host acceptance.
