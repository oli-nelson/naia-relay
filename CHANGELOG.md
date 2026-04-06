# Changelog

All notable changes to `naia-relay` should be documented in this file.

This project is still in an early stage, so the changelog currently focuses on
major implementation milestones rather than formal versioned releases.

## Unreleased

### Added

- MCP, TEP, and RLP runtime foundations
- direct, host, and client relay roles
- stdio, TCP, and HTTP transport support where applicable
- readiness-file support for dynamic listener discovery
- protocol reference docs for TEP and RLP
- subprocess and integration coverage for direct and bridged topologies
- bridged executor forwarding over TEP stdio
- structured TEP validation error responses

### Changed

- MCP stdio behavior aligned with newline-delimited JSON
- direct dual-stdio configuration is explicitly rejected
- public-facing README and operator/developer documentation expanded

### Fixed

- client relay startup auto-bind behavior
- host-side TEP stdio serving
- bridged tool execution now reaches the real executor path
- Lua/Neovim empty-table interoperability for TEP object-bag fields
