"""
Claude CLI Provider Implementation

Claude Code CLI を使用した Provider 実装。
Amplifier Core の Provider プロトコルに完全準拠。

2つのモードをサポート:
- passthrough: CLIに全て任せる
- controlled: ツール実行をAmplifier側で制御（推奨）
"""

import asyncio
import json
import logging
import re
import subprocess
from typing import Any, Literal

from amplifier_core import (
    ChatRequest,
    ChatResponse,
    Message,
    TextBlock,
    ToolCallBlock,
    ToolSpec,
)
from amplifier_core.message_models import ToolCall
from amplifier_core.models import ToolCall as ModelToolCall

logger = logging.getLogger(__name__)


class ClaudeCliProvider:
    """
    Claude Code CLI を使用する Provider。

    ローカルで認証済みの `claude` コマンドを呼び出して
    LLM とやり取りします。APIキーは不要です。

    Provider プロトコル実装:
        - name: プロバイダー識別子
        - complete(request, **kwargs): チャット補完を生成
        - parse_tool_calls(response): ツールコールを抽出
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize Claude CLI Provider.

        Args:
            config: Configuration dictionary
                - mode: "passthrough" (default) or "controlled"
                - model: Model name (e.g., "sonnet", "opus")
                - timeout: Timeout in seconds (default: 300)
                - name: Provider name override (default: "claude-cli")
        """
        self._mode: Literal["passthrough", "controlled"] = config.get("mode", "controlled")
        self._model = config.get("model")
        self._timeout = config.get("timeout", 300)
        self._name = config.get("name", "claude-cli")

        # Statistics
        self.request_count = 0
        self.total_duration_ms = 0

        # Verify CLI availability
        self._verify_cli()

        logger.info(f"ClaudeCliProvider initialized: mode={self._mode}, model={self._model}")

    def _verify_cli(self) -> None:
        """Verify Claude CLI is available and working."""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("Claude CLI returned non-zero exit code")
            self._version = result.stdout.strip()
            logger.info(f"Claude CLI version: {self._version}")
        except FileNotFoundError:
            raise RuntimeError(
                "Claude CLI not found. Please install Claude Code: "
                "https://docs.anthropic.com/claude-code"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude CLI timed out during version check")

    @property
    def name(self) -> str:
        """Provider identifier."""
        return self._name

    @property
    def version(self) -> str:
        """Claude CLI version."""
        return self._version

    @property
    def mode(self) -> str:
        """Operating mode."""
        return self._mode

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """
        Generate chat completion using Claude CLI.

        Args:
            request: ChatRequest with messages and optional tools
            **kwargs: Additional options
                - model: Override configured model

        Returns:
            ChatResponse with content and optional tool_calls
        """
        self.request_count += 1
        logger.debug(f"Processing request #{self.request_count}")

        if self._mode == "controlled":
            return await self._complete_controlled(request, **kwargs)
        else:
            return await self._complete_passthrough(request, **kwargs)

    async def _complete_passthrough(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """Passthrough mode: let CLI handle everything."""
        prompt = self._build_simple_prompt(request.messages)
        system_prompt = self._extract_system_prompt(request.messages)

        cmd = self._build_command(prompt, system_prompt, **kwargs)

        return await self._execute_cli(cmd, has_tools=False)

    async def _complete_controlled(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """Controlled mode: disable CLI tools, handle tool calls in Amplifier."""
        prompt = self._build_prompt_with_tools(request)
        system_prompt = self._build_system_prompt_for_tools(request)

        cmd = self._build_command(prompt, system_prompt, tools_disabled=True, **kwargs)

        return await self._execute_cli(cmd, has_tools=bool(request.tools))

    def _build_command(
        self,
        prompt: str,
        system_prompt: str | None = None,
        tools_disabled: bool = False,
        **kwargs
    ) -> list[str]:
        """Build CLI command with arguments."""
        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
        ]

        if tools_disabled:
            cmd.extend(["--tools", ""])

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        model = kwargs.get("model") or self._model
        if model:
            cmd.extend(["--model", model])

        return cmd

    async def _execute_cli(self, cmd: list[str], has_tools: bool) -> ChatResponse:
        """Execute CLI command and parse response."""
        logger.debug(f"Executing CLI command")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"CLI timeout after {self._timeout}s")
            return ChatResponse(
                content=[TextBlock(type="text", text=f"Error: Timeout after {self._timeout}s")],
                finish_reason="error",
            )

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            logger.error(f"CLI error: {error_msg}")
            return ChatResponse(
                content=[TextBlock(type="text", text=f"Error: {error_msg}")],
                finish_reason="error",
            )

        output = stdout.decode("utf-8", errors="replace")
        return self._parse_response(output, has_tools)

    def parse_tool_calls(self, response: ChatResponse) -> list[ModelToolCall]:
        """
        Extract tool calls from response.

        Args:
            response: ChatResponse from complete()

        Returns:
            List of ToolCall objects
        """
        tool_calls = []

        for block in response.content:
            if isinstance(block, ToolCallBlock):
                tool_calls.append(
                    ModelToolCall(
                        tool=block.name,
                        arguments=block.input,
                        id=block.id,
                    )
                )

        return tool_calls

    def _extract_system_prompt(self, messages: list[Message]) -> str | None:
        """Extract system message from messages."""
        for msg in messages:
            if msg.role == "system":
                return self._extract_text(msg.content)
        return None

    def _build_simple_prompt(self, messages: list[Message]) -> str:
        """Build simple prompt for passthrough mode."""
        parts = []
        for msg in messages:
            if msg.role == "system":
                continue
            elif msg.role == "user":
                parts.append(self._extract_text(msg.content))
            elif msg.role == "assistant":
                parts.append(f"[Previous response]\n{self._extract_text(msg.content)}")
        return "\n\n".join(parts)

    def _build_system_prompt_for_tools(self, request: ChatRequest) -> str | None:
        """Build system prompt with tool format instructions."""
        parts = []

        # Original system message
        system = self._extract_system_prompt(request.messages)
        if system:
            parts.append(system)

        # Add tool format instructions if tools are provided
        if request.tools:
            parts.append(self._get_tool_format_instruction())

        return "\n\n".join(parts) if parts else None

    def _get_tool_format_instruction(self) -> str:
        """Get instructions for tool call format."""
        return """When you need to use a tool, respond with a JSON block in this exact format:
```tool_call
{
  "tool": "tool_name",
  "arguments": {
    "arg1": "value1"
  }
}
```

You can include text before or after the tool_call block.
If you don't need to use a tool, respond normally without any tool_call block."""

    def _build_prompt_with_tools(self, request: ChatRequest) -> str:
        """Build prompt including tool definitions."""
        parts = []

        # Tool definitions
        if request.tools:
            parts.append(f"Available tools:\n{self._format_tools(request.tools)}")

        # Messages
        for msg in request.messages:
            if msg.role == "system":
                continue
            elif msg.role == "user":
                parts.append(self._extract_text(msg.content))
            elif msg.role == "assistant":
                parts.append(f"[Assistant]: {self._extract_text(msg.content)}")
            elif msg.role == "tool":
                parts.append(f"[Tool Result]: {self._extract_text(msg.content)}")

        return "\n\n".join(parts)

    def _format_tools(self, tools: list[ToolSpec]) -> str:
        """Format tool definitions for prompt."""
        lines = []
        for tool in tools:
            lines.append(f"- {tool.name}: {tool.description or 'No description'}")
            if tool.parameters:
                props = tool.parameters.get("properties", {})
                required = tool.parameters.get("required", [])
                for prop_name, prop_def in props.items():
                    req = "*" if prop_name in required else ""
                    desc = prop_def.get("description", "")
                    ptype = prop_def.get("type", "any")
                    lines.append(f"    - {prop_name}{req} ({ptype}): {desc}")
        return "\n".join(lines)

    def _extract_text(self, content) -> str:
        """Extract text from content (string or list of blocks)."""
        if isinstance(content, str):
            return content
        texts = []
        for block in content:
            if isinstance(block, TextBlock):
                texts.append(block.text)
            elif hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts)

    def _parse_response(self, output: str, has_tools: bool) -> ChatResponse:
        """Parse CLI JSON output into ChatResponse."""
        result_text = ""
        metadata = {}

        # Extract result from JSON output
        try:
            lines = output.strip().split("\n")
            for line in reversed(lines):
                try:
                    data = json.loads(line)
                    if data.get("type") == "result":
                        result_text = data.get("result", "")
                        metadata = {
                            "cost_usd": data.get("cost_usd"),
                            "duration_ms": data.get("duration_ms"),
                            "session_id": data.get("session_id"),
                        }
                        if metadata.get("duration_ms"):
                            self.total_duration_ms += metadata["duration_ms"]
                        break
                except json.JSONDecodeError:
                    continue
        except Exception:
            result_text = output

        # Detect tool calls in controlled mode
        content_blocks = []
        tool_calls = []

        if has_tools and self._mode == "controlled":
            tool_call_pattern = r"```tool_call\s*\n(.*?)\n```"
            matches = re.findall(tool_call_pattern, result_text, re.DOTALL)

            remaining = result_text
            for match in matches:
                try:
                    tc_data = json.loads(match)
                    tc_id = f"tc_{len(tool_calls)+1}"

                    content_blocks.append(ToolCallBlock(
                        type="tool_call",
                        id=tc_id,
                        name=tc_data.get("tool"),
                        input=tc_data.get("arguments", {}),
                    ))
                    tool_calls.append(ToolCall(
                        id=tc_id,
                        name=tc_data.get("tool"),
                        arguments=tc_data.get("arguments", {}),
                    ))
                    remaining = remaining.replace(f"```tool_call\n{match}\n```", "")
                except json.JSONDecodeError:
                    continue

            remaining = remaining.strip()
            if remaining:
                content_blocks.insert(0, TextBlock(type="text", text=remaining))
        else:
            content_blocks.append(TextBlock(type="text", text=result_text))

        finish_reason = "tool_use" if tool_calls else "stop"

        return ChatResponse(
            content=content_blocks,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason=finish_reason,
            metadata=metadata,
        )
