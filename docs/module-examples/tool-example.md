# Tool実装例

ToolはLLMが呼び出せる機能を提供するモジュールです。

## Toolプロトコル

**定義:** `interfaces.py:98-122`

```python
@runtime_checkable
class Tool(Protocol):
    @property
    def name(self) -> str:
        """ツール名（LLMが呼び出すときに使用）"""
        ...

    @property
    def description(self) -> str:
        """ツールの説明（LLMに提供）"""
        ...

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """
        ツールを実行。

        Args:
            input: ツール固有の入力パラメータ

        Returns:
            ToolResult
        """
        ...
```

## 実装例1: Bash Tool

```python
"""
Bash Tool モジュール

シェルコマンドを実行するツールです。
"""

import asyncio
import logging
from typing import Any

from amplifier_core import ToolResult
from amplifier_core.coordinator import ModuleCoordinator

logger = logging.getLogger(__name__)


class BashTool:
    """シェルコマンド実行ツール"""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - timeout: コマンドタイムアウト秒数（デフォルト: 30）
                - allowed_commands: 許可するコマンドのリスト（デフォルト: すべて）
                - working_directory: 作業ディレクトリ（デフォルト: カレントディレクトリ）
        """
        self.name = "bash"
        self.description = (
            "Execute shell commands. "
            "Use this to run bash commands, scripts, and interact with the system."
        )

        self._timeout = config.get("timeout", 30)
        self._allowed_commands = config.get("allowed_commands")
        self._working_directory = config.get("working_directory", ".")

        # 統計
        self.execution_count = 0
        self.failure_count = 0
        self.total_duration = 0.0

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """
        シェルコマンドを実行。

        Args:
            input: 入力パラメータ
                - command: 実行するコマンド（必須）

        Returns:
            ToolResult
                - output: コマンドの標準出力と標準エラー出力
                - error: エラーが発生した場合のエラー情報
        """
        self.execution_count += 1

        command = input.get("command")
        if not command:
            self.failure_count += 1
            return ToolResult(
                success=False,
                error={"message": "Command is required"}
            )

        # コマンド検証
        if self._allowed_commands:
            cmd_name = command.split()[0]
            if cmd_name not in self._allowed_commands:
                self.failure_count += 1
                return ToolResult(
                    success=False,
                    error={"message": f"Command '{cmd_name}' is not allowed"}
                )

        logger.info(f"Executing command: {command}")

        try:
            import time
            start_time = time.time()

            # コマンド実行
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._working_directory
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                self.failure_count += 1

                return ToolResult(
                    success=False,
                    error={
                        "message": f"Command timed out after {self._timeout}s",
                        "type": "TimeoutError"
                    }
                )

            duration = time.time() - start_time
            self.total_duration += duration

            # 出力の結合
            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n[stderr]\n" + stderr.decode("utf-8", errors="replace")

            # 終了コードのチェック
            if process.returncode != 0:
                self.failure_count += 1
                return ToolResult(
                    success=False,
                    output=output,
                    error={
                        "message": f"Command failed with exit code {process.returncode}",
                        "exit_code": process.returncode
                    }
                )

            logger.info(f"Command completed in {duration:.2f}s")

            return ToolResult(
                success=True,
                output=output
            )

        except Exception as e:
            self.failure_count += 1
            logger.error(f"Command execution failed: {e}")

            return ToolResult(
                success=False,
                error={
                    "message": str(e),
                    "type": type(e).__name__
                }
            )

    def get_tool_spec(self) -> dict:
        """LLMに渡すツール仕様を生成"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }


async def mount(coordinator: ModuleCoordinator, config: dict):
    """
    Bash Toolをマウント。

    Args:
        coordinator: ModuleCoordinator
        config: 設定

    Returns:
        cleanup関数
    """
    logger.info("Mounting Bash tool")

    # Toolインスタンス作成
    tool = BashTool(config)

    # Coordinatorにマウント
    await coordinator.mount("tools", tool, name="bash")

    # カスタムイベントを宣言
    coordinator.register_contributor(
        "observability.events",
        "tool-bash",
        lambda: [
            "bash:execute",
            "bash:complete",
            "bash:timeout",
            "bash:killed"
        ]
    )

    # メトリクスをコントリビューション
    coordinator.register_contributor(
        "metrics.tools",
        "tool-bash",
        lambda: {
            "name": "bash",
            "executions": tool.execution_count,
            "failures": tool.failure_count,
            "avg_duration": (
                tool.total_duration / tool.execution_count
                if tool.execution_count > 0
                else 0
            )
        }
    )

    logger.info("Bash tool mounted successfully")

    # クリーンアップ不要
    return None
```

## 実装例2: Filesystem Tool

```python
"""
Filesystem Tool モジュール

ファイルシステム操作を提供するツールです。
"""

import logging
import os
from pathlib import Path
from typing import Any

from amplifier_core import ToolResult
from amplifier_core.coordinator import ModuleCoordinator

logger = logging.getLogger(__name__)


class FilesystemTool:
    """ファイルシステム操作ツール"""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - allowed_paths: 許可するパスのリスト（デフォルト: カレントディレクトリ）
                - max_file_size: 読み込み可能な最大ファイルサイズ（バイト、デフォルト: 1MB）
        """
        self.name = "filesystem"
        self.description = (
            "Read and write files on the filesystem. "
            "Use this to read file contents, write to files, list directories, etc."
        )

        self._allowed_paths = [
            Path(p).resolve() for p in config.get("allowed_paths", ["."])
        ]
        self._max_file_size = config.get("max_file_size", 1024 * 1024)  # 1MB

        # 統計
        self.read_count = 0
        self.write_count = 0

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """
        ファイルシステム操作を実行。

        Args:
            input: 入力パラメータ
                - operation: 操作タイプ（"read", "write", "list"）
                - path: ファイルパス
                - content: 書き込み内容（writeの場合）

        Returns:
            ToolResult
        """
        operation = input.get("operation")
        path_str = input.get("path")

        if not operation or not path_str:
            return ToolResult(
                success=False,
                error={"message": "operation and path are required"}
            )

        path = Path(path_str).resolve()

        # パス検証
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                error={
                    "message": f"Access to path '{path}' is not allowed",
                    "allowed_paths": [str(p) for p in self._allowed_paths]
                }
            )

        try:
            if operation == "read":
                return await self._read_file(path)
            elif operation == "write":
                return await self._write_file(path, input.get("content", ""))
            elif operation == "list":
                return await self._list_directory(path)
            else:
                return ToolResult(
                    success=False,
                    error={"message": f"Unknown operation: {operation}"}
                )

        except Exception as e:
            logger.error(f"Filesystem operation failed: {e}")
            return ToolResult(
                success=False,
                error={
                    "message": str(e),
                    "type": type(e).__name__
                }
            )

    def _is_path_allowed(self, path: Path) -> bool:
        """パスが許可されているかチェック"""
        for allowed in self._allowed_paths:
            try:
                path.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False

    async def _read_file(self, path: Path) -> ToolResult:
        """ファイルを読み込み"""
        if not path.is_file():
            return ToolResult(
                success=False,
                error={"message": f"File not found: {path}"}
            )

        # サイズチェック
        file_size = path.stat().st_size
        if file_size > self._max_file_size:
            return ToolResult(
                success=False,
                error={
                    "message": f"File too large: {file_size} bytes (max: {self._max_file_size})"
                }
            )

        self.read_count += 1
        content = path.read_text(encoding="utf-8", errors="replace")

        logger.info(f"Read file: {path} ({file_size} bytes)")

        return ToolResult(
            success=True,
            output={
                "path": str(path),
                "content": content,
                "size": file_size
            }
        )

    async def _write_file(self, path: Path, content: str) -> ToolResult:
        """ファイルに書き込み"""
        self.write_count += 1
        path.write_text(content, encoding="utf-8")

        logger.info(f"Wrote file: {path} ({len(content)} chars)")

        return ToolResult(
            success=True,
            output={
                "path": str(path),
                "bytes_written": len(content.encode("utf-8"))
            }
        )

    async def _list_directory(self, path: Path) -> ToolResult:
        """ディレクトリの内容をリスト"""
        if not path.is_dir():
            return ToolResult(
                success=False,
                error={"message": f"Not a directory: {path}"}
            )

        entries = []
        for entry in path.iterdir():
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None
            })

        logger.info(f"Listed directory: {path} ({len(entries)} entries)")

        return ToolResult(
            success=True,
            output={
                "path": str(path),
                "entries": entries
            }
        )

    def get_tool_spec(self) -> dict:
        """LLMに渡すツール仕様を生成"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "list"],
                        "description": "The filesystem operation to perform"
                    },
                    "path": {
                        "type": "string",
                        "description": "The file or directory path"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (for write operation)"
                    }
                },
                "required": ["operation", "path"]
            }
        }


async def mount(coordinator: ModuleCoordinator, config: dict):
    """Filesystem Toolをマウント"""
    logger.info("Mounting Filesystem tool")

    tool = FilesystemTool(config)
    await coordinator.mount("tools", tool, name="filesystem")

    # カスタムイベントを宣言
    coordinator.register_contributor(
        "observability.events",
        "tool-filesystem",
        lambda: ["filesystem:read", "filesystem:write", "filesystem:list"]
    )

    # メトリクスをコントリビューション
    coordinator.register_contributor(
        "metrics.tools",
        "tool-filesystem",
        lambda: {
            "name": "filesystem",
            "reads": tool.read_count,
            "writes": tool.write_count
        }
    )

    logger.info("Filesystem tool mounted successfully")
    return None
```

## 使用例

```python
config = {
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple"
    },
    "providers": [
        {"module": "provider-anthropic", "config": {"api_key": "..."}}
    ],
    "tools": [
        {
            "module": "tool-bash",
            "config": {
                "timeout": 60,
                "allowed_commands": ["ls", "cat", "grep", "find"]
            }
        },
        {
            "module": "tool-filesystem",
            "config": {
                "allowed_paths": ["/home/user/project"],
                "max_file_size": 5242880  # 5MB
            }
        }
    ]
}

session = AmplifierSession(config)
await session.initialize()

result = await session.execute("List all Python files in the current directory")
```

## エントリーポイント設定

**pyproject.toml:**

```toml
[project.entry-points."amplifier.modules"]
tool-bash = "amplifier_module_tool_bash:mount"
tool-filesystem = "amplifier_module_tool_filesystem:mount"
```

## 次のステップ

- [Orchestrator実装例](./orchestrator-example.md)でツールの呼び出し方を確認
- [Hook実装例](./hook-example.md)でツール実行の監視方法を学ぶ
