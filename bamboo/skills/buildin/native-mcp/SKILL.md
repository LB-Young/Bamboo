---
name: native-mcp
description: Configure and troubleshoot Bamboo native MCP stdio servers and MCP-discovered tools.
user-invocable: true
load-experiences: true
metadata:
  bamboo:
    tags:
      - mcp
      - tools
      - configuration
---

# Native MCP

## When to Use

Use this skill when the user wants to configure, debug, or reason about Bamboo MCP servers and tools.

## Bamboo MCP Model

Bamboo starts configured stdio MCP servers from runtime configuration, discovers their tools, wraps each discovered tool as a Bamboo Tool, and routes execution through ToolRegistry, PermissionPolicy, EventBus, and audit logging.

## Workflow

1. Inspect `bamboo/configs/mcp.yaml` or the task config for MCP server entries.
2. Check command, args, environment, and timeout settings.
3. Confirm discovered tool names use the `mcp_<server>_<tool>` shape.
4. Treat MCP tools as external capabilities. Network or unknown risk tools should require permission.
5. Debug startup failures by checking server command availability, JSON-RPC initialization, and stderr output.

## Boundaries

This skill explains MCP usage. It does not implement MCP and does not replace MCP-discovered tools.
