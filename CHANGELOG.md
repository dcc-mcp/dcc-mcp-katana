# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Features

- expand the Katana node graph skill to 17 bounded typed tools
- add typed node, parameter, port, selection, timeline, and verified-save workflows
- add package resource diagnostics and a real-host typed CLI smoke test

### Security

- cap pending main-thread calls, node results, selection, deletion, and parameter payloads
- require explicit confirmation for destructive node and port removal
- restrict project output to allowlisted absolute `.katana` paths with opt-in overwrite

### Fixed

- distinguish cancelled pre-execution timeouts from unknown post-start host outcomes
- cleanly roll back dispatcher and server lifecycle failures
- ensure tests import the active checkout instead of an unrelated editable installation

## [0.3.0](https://github.com/dcc-mcp/dcc-mcp-katana/compare/v0.2.0...v0.3.0) (2026-07-16)


### Features

* default adapter instances to dynamic ports ([#2](https://github.com/dcc-mcp/dcc-mcp-katana/issues/2)) ([655c0bf](https://github.com/dcc-mcp/dcc-mcp-katana/commit/655c0bf9c919c716fba3761768ed1f70e1449325))

## [0.2.0](https://github.com/dcc-mcp/dcc-mcp-katana/compare/v0.1.0...v0.2.0) (2026-07-14)


### Features

* add Katana MCP adapter ([eb633db](https://github.com/dcc-mcp/dcc-mcp-katana/commit/eb633dbb93ac94bfccb045b20591e3388e2593b2))


### Bug Fixes

* parse release manifest in version test ([02934c3](https://github.com/dcc-mcp/dcc-mcp-katana/commit/02934c3d92eb7beda116132b94d20f93c7c5e968))
* use valid CI expression syntax ([4b15be5](https://github.com/dcc-mcp/dcc-mcp-katana/commit/4b15be5ad17743d06e38fdc5923240c700820afb))

## [0.1.0] - 2026-07-14

### Added

- Initial Katana MCP adapter with typed NodegraphAPI tools.
