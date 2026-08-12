# Architecture

## Ownership boundaries

- `DccServerBase` owns MCP, REST readiness, discovery, jobs, and skill loading.
- `KatanaDispatcher` owns the bounded crossing onto Katana's event-processing thread.
- `operations.py` owns host validation and calls only the official `NodegraphAPI` and
  `KatanaFile` surfaces.
- `tools.yaml` owns the public typed contract; scripts only adapt that contract to
  DCC-MCP result envelopes.
- Katana continues to own node behavior, parameter semantics, project serialization,
  licensing, rendering, and plug-in node types.

## Execution sequence

1. Katana discovers `katana_plugin/Plugins/dcc_mcp_katana.py` through
   `KATANA_RESOURCES`.
2. The plug-in installs one native event handler, constructs the in-host server, and
   registers the progressive `katana-nodegraph` skill.
3. A typed call reaches `HostExecutionBridge` on a server worker.
4. `KatanaDispatcher` reserves one of 32 pending slots and queues the call through
   `Utils.EventModule.QueueEvent`.
5. The event handler performs validated `NodegraphAPI` or `KatanaFile` work and returns
   a JSON-serializable result.

Calls made on Katana's main thread execute directly. A queued call that times out
before starting is marked cancelled and skipped when its event arrives. A call that
times out after starting reports an unknown host outcome, because killing host API
work would violate Katana's ownership boundary.

## Security and resource limits

The public contract has no raw Python, parameter-expression, Script Button, shell,
or render-script entry point. Node and port names are bounded and reject control
characters. List responses, selection, deletion, parameter children, parameter text,
and pending host work all have explicit limits. Destructive deletion requires a
boolean confirmation.

Project output is restricted to absolute `.katana` paths under
`DCC_MCP_KATANA_ALLOWED_ROOTS`. Overwrite and parent creation are separate opt-ins.
Successful saves are verified from disk and return bytes plus SHA-256.

## Validation boundary

Unit tests use a contract-compatible fake of the documented Katana APIs to verify
validation, lifecycle, queue, timeout, and serialization behavior on Python 3.9 and
3.12. They are not live-host proof. `tools/live_katana_smoke.py` is the acceptance
path for a licensed Katana host and deliberately uses the typed DCC-MCP CLI rather
than importing operations directly.
