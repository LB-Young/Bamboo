"""同步 stdio MCP JSON-RPC client。

第一版使用 newline-delimited JSON-RPC，和当前 Auton 参考实现保持一致。
后续如果要兼容 Content-Length framing，可以在本模块内扩展读写协议，
不影响 ToolRegistry 和 MCPDiscoveredTool 的接口。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from typing import Any

from bamboo.helpers.redact import redact_sensitive_text
from bamboo.tools.buildin.base import ToolResult
from bamboo.tools.mcp.models import MCPServerConfig, MCPToolDefinition

_SAFE_ENV_KEYS = {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "SHELL", "TMPDIR"}
_ENV_REFERENCE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class MCPClient:
    """通过 stdio 与一个 MCP server 通信。"""

    def __init__(self, config: MCPServerConfig) -> None:
        """保存 server 配置。"""
        self.config = config
        self._process: subprocess.Popen[str] | None = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._tools: list[MCPToolDefinition] = []
        self._initialized = False

    def start(self) -> None:
        """启动 MCP server 并加载工具列表。"""
        if self._initialized:
            return
        command = [self.config.command, *self.config.args]
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self._build_env(),
        )
        self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"roots": {}, "sampling": {}},
                "clientInfo": {"name": "bamboo", "version": "0.1.0"},
            },
        )
        self._send_notification("initialized", {})
        self._initialized = True
        self._tools = self.list_tools()

    def list_tools(self) -> list[MCPToolDefinition]:
        """调用 tools/list 并返回工具定义。"""
        result = self._send_request("tools/list", {})
        raw_tools = result.get("tools", [])
        if not isinstance(raw_tools, list):
            return []
        tools: list[MCPToolDefinition] = []
        for raw_tool in raw_tools:
            if not isinstance(raw_tool, dict):
                continue
            name = raw_tool.get("name")
            if not isinstance(name, str) or not name:
                continue
            input_schema = raw_tool.get("inputSchema", {})
            tools.append(
                MCPToolDefinition(
                    server=self.config.name,
                    name=name,
                    description=str(raw_tool.get("description") or ""),
                    input_schema=input_schema if isinstance(input_schema, dict) else {},
                )
            )
        return tools

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """调用远端 MCP 工具。"""
        if not self._initialized:
            self.start()
        try:
            result = self._send_request(
                "tools/call",
                {"name": tool_name, "arguments": arguments or {}},
            )
        except Exception as exc:
            error = redact_sensitive_text(str(exc))
            return ToolResult(content=error, success=False, error=error)
        return ToolResult(content=self._extract_text(result), metadata={"raw_result": result})

    @property
    def tools(self) -> list[MCPToolDefinition]:
        """返回已发现的工具。"""
        return list(self._tools)

    def stop(self) -> None:
        """停止 MCP server 进程。"""
        if self._process is None:
            return
        try:
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=5)
        finally:
            self._process = None
            self._initialized = False
            self._tools = []

    def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """发送 JSON-RPC request 并读取 response。"""
        with self._lock:
            process = self._require_process()
            self._request_id += 1
            request_id = self._request_id
            request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            assert process.stdin is not None
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()

            assert process.stdout is not None
            while True:
                line = process.stdout.readline()
                if not line:
                    stderr = self._read_stderr_preview(process)
                    raise RuntimeError(f"MCP server {self.config.name} closed stdout: {stderr}")
                response = json.loads(line)
                if response.get("id") != request_id:
                    continue
                if "error" in response:
                    raise RuntimeError(response["error"])
                result = response.get("result", {})
                return result if isinstance(result, dict) else {"value": result}

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        """发送 JSON-RPC notification。"""
        process = self._require_process()
        notification = {"jsonrpc": "2.0", "method": method, "params": params}
        assert process.stdin is not None
        process.stdin.write(json.dumps(notification) + "\n")
        process.stdin.flush()

    def _require_process(self) -> subprocess.Popen[str]:
        """返回已启动进程。"""
        if self._process is None or self._process.poll() is not None:
            raise RuntimeError(f"MCP server {self.config.name} is not running")
        return self._process

    def _build_env(self) -> dict[str, str]:
        """构造安全的 MCP 子进程环境。"""
        env = {key: value for key, value in os.environ.items() if key in _SAFE_ENV_KEYS or key.startswith("XDG_")}
        for key, value in self.config.env.items():
            env[key] = _resolve_env_value(value)
        return env

    def _extract_text(self, result: dict[str, Any]) -> str:
        """从 MCP tools/call result 提取文本内容。"""
        content = result.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            return redact_sensitive_text("\n".join(part for part in parts if part))
        return redact_sensitive_text(json.dumps(result, ensure_ascii=False, sort_keys=True))

    def _read_stderr_preview(self, process: subprocess.Popen[str]) -> str:
        """读取一段 stderr 预览并脱敏。"""
        if process.stderr is None:
            return ""
        try:
            return redact_sensitive_text(process.stderr.read(500))
        except OSError:
            return ""


def _resolve_env_value(value: str) -> str:
    """解析 ${ENV_NAME} 形式的显式环境变量引用。"""
    match = _ENV_REFERENCE.fullmatch(value)
    if match is None:
        return value
    return os.environ.get(match.group(1), "")
