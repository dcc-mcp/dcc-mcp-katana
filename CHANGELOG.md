# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0](https://github.com/dcc-mcp/dcc-mcp-katana/compare/v0.4.0...v0.5.0) (2026-08-25)


### Features

* adopt agent-first install lifecycle ([247ebd2](https://github.com/dcc-mcp/dcc-mcp-katana/commit/247ebd270a813edd7b3f44a34cdca7439cd4b073))

## [0.4.0](https://github.com/dcc-mcp/dcc-mcp-katana/compare/v0.3.0...v0.4.0) (2026-08-12)


### Features

* ship production-ready Katana nodegraph workflows ([#6](https://github.com/dcc-mcp/dcc-mcp-katana/issues/6)) ([a63e956](https://github.com/dcc-mcp/dcc-mcp-katana/commit/a63e956315113c6ad4a3d184a1c06cdfd5bab92d))


### Documentation

* align agent workflow and branding ([738c846](https://github.com/dcc-mcp/dcc-mcp-katana/commit/738c846d3ecc63b892f0d837cef4f088c3ab65cb))
* document CLI install and updates ([84ff8bd](https://github.com/dcc-mcp/dcc-mcp-katana/commit/84ff8bd6cb4d1c21dbc548e8acba68bc64409923))

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
