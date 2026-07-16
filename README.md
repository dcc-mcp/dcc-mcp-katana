# dcc-mcp-katana

MCP adapter for Foundry Katana. It runs typed NodegraphAPI operations on Katana's event-processing thread.

```bash
pip install dcc-mcp-katana
```

Add the installed `dcc_mcp_katana/katana_plugin` directory to `KATANA_RESOURCES`, then start Katana. Each adapter instance uses an OS-assigned port and registers it for CLI discovery. Connect through the stable gateway at `http://127.0.0.1:9765/mcp`; set `DCC_MCP_KATANA_PORT` only when a fixed direct endpoint is required.

## Tools

- `katana-nodegraph.inspect_nodegraph`
- `katana-nodegraph.list_nodes`
- `katana-nodegraph.save_project`

`save_project` changes files and requires an absolute `.katana` path.
