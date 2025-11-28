# Hook実装例

Hookモジュールはライフサイクルイベントを観測し、動作を制御するモジュールです。

## HookHandlerプロトコル

**定義:** `interfaces.py:150-165`

```python
@runtime_checkable
class HookHandler(Protocol):
    async def __call__(self, event: str, data: dict[str, Any]) -> HookResult:
        """
        ライフサイクルイベントを処理。

        Args:
            event: イベント名
            data: イベントデータ

        Returns:
            HookResult
        """
        ...
```

## 実装例1: ロギングフック

```python
"""
Logging Hook モジュール

すべてのイベントをログに記録するフックです。
"""

import json
import logging
from pathlib import Path
from typing import Any

from amplifier_core import HookResult
from amplifier_core.coordinator import ModuleCoordinator
from amplifier_core.events import ALL_EVENTS

logger = logging.getLogger(__name__)


class LoggingHook:
    """ロギングフック"""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - log_file: ログファイルパス（デフォルト: None、標準ログのみ）
                - log_events: ログするイベントのリスト（デフォルト: すべて）
                - log_level: ログレベル（デフォルト: INFO）
        """
        self._log_file = config.get("log_file")
        self._log_events = config.get("log_events", ALL_EVENTS)
        self._log_level = config.get("log_level", "INFO")

        if self._log_file:
            self._log_file_path = Path(self._log_file)
            self._log_file_path.parent.mkdir(parents=True, exist_ok=True)

    async def handle_event(self, event: str, data: dict) -> HookResult:
        """イベントを処理"""
        if event not in self._log_events:
            return HookResult(action="continue")

        # ログエントリを構築
        log_entry = {
            "event": event,
            "session_id": data.get("session_id"),
            "data": self._sanitize_data(data)
        }

        # 標準ログに記録
        logger.log(
            getattr(logging, self._log_level),
            f"[{event}] {json.dumps(log_entry, default=str)}"
        )

        # ファイルに記録
        if self._log_file:
            with self._log_file_path.open("a") as f:
                f.write(json.dumps(log_entry, default=str) + "\n")

        return HookResult(action="continue")

    def _sanitize_data(self, data: dict) -> dict:
        """機密データを削除"""
        sanitized = data.copy()

        # APIキーなどを削除
        sensitive_keys = ["api_key", "password", "token", "secret"]

        for key in list(sanitized.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"

        return sanitized


async def mount(coordinator: ModuleCoordinator, config: dict):
    """Logging Hookをマウント"""
    logger.info("Mounting Logging hook")

    hook = LoggingHook(config)

    # すべてのイベントに登録
    for event in ALL_EVENTS:
        coordinator.hooks.register(
            event,
            hook.handle_event,
            priority=999,  # 最後に実行（他のフックの影響を受けない）
            name="logging-hook"
        )

    logger.info("Logging hook mounted successfully")

    return None
```

## 実装例2: セキュリティフック

```python
"""
Security Hook モジュール

危険な操作をブロックするセキュリティフックです。
"""

import logging
import re
from typing import Any

from amplifier_core import HookResult
from amplifier_core.coordinator import ModuleCoordinator
from amplifier_core.events import TOOL_PRE

logger = logging.getLogger(__name__)


class SecurityHook:
    """セキュリティフック"""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - blocked_commands: ブロックするコマンドパターンのリスト
                - protected_paths: 保護するパスのリスト
                - require_approval: 承認が必要な操作のリスト
        """
        self._blocked_commands = config.get("blocked_commands", [
            r"rm\s+-rf\s+/",
            r":(){ :|:& };:",  # Fork bomb
            r"mkfs",
            r"dd\s+if=.*of=/dev/",
        ])

        self._protected_paths = config.get("protected_paths", [
            "/etc",
            "/sys",
            "/proc",
            "/boot"
        ])

        self._require_approval = config.get("require_approval", [
            "production",
            "database",
            "config"
        ])

    async def handle_tool_pre(self, event: str, data: dict) -> HookResult:
        """ツール実行前のセキュリティチェック"""
        tool = data.get("tool")
        arguments = data.get("arguments", {})

        # Bashコマンドのチェック
        if tool == "bash":
            return await self._check_bash_command(arguments)

        # ファイルシステム操作のチェック
        if tool == "filesystem":
            return await self._check_filesystem_operation(arguments)

        return HookResult(action="continue")

    async def _check_bash_command(self, arguments: dict) -> HookResult:
        """Bashコマンドのセキュリティチェック"""
        command = arguments.get("command", "")

        # 危険なコマンドパターンをチェック
        for pattern in self._blocked_commands:
            if re.search(pattern, command):
                logger.warning(f"Blocked dangerous command: {command}")
                return HookResult(
                    action="deny",
                    reason=f"Command matches blocked pattern: {pattern}"
                )

        return HookResult(action="continue")

    async def _check_filesystem_operation(self, arguments: dict) -> HookResult:
        """ファイルシステム操作のセキュリティチェック"""
        operation = arguments.get("operation")
        path = arguments.get("path", "")

        # 保護されたパスへの書き込みをチェック
        if operation == "write":
            for protected in self._protected_paths:
                if path.startswith(protected):
                    logger.warning(f"Blocked write to protected path: {path}")
                    return HookResult(
                        action="deny",
                        reason=f"Write to protected path: {protected}"
                    )

        # 承認が必要な操作
        if operation in ["write", "delete"]:
            for keyword in self._require_approval:
                if keyword in path.lower():
                    logger.info(f"Requesting approval for: {path}")
                    return HookResult(
                        action="ask_user",
                        approval_prompt=f"Allow {operation} to {path}?",
                        approval_options=["Allow once", "Deny"],
                        approval_timeout=60.0,
                        approval_default="deny"
                    )

        return HookResult(action="continue")


async def mount(coordinator: ModuleCoordinator, config: dict):
    """Security Hookをマウント"""
    logger.info("Mounting Security hook")

    hook = SecurityHook(config)

    # ツール実行前イベントに登録（高優先度）
    coordinator.hooks.register(
        TOOL_PRE,
        hook.handle_tool_pre,
        priority=0,  # 最初に実行
        name="security-hook"
    )

    logger.info("Security hook mounted successfully")

    return None
```

## 実装例3: Linterフック

```python
"""
Linter Hook モジュール

ファイル書き込み後にLintを実行し、エラーをコンテキストに注入するフックです。
"""

import asyncio
import logging
from typing import Any

from amplifier_core import HookResult
from amplifier_core.coordinator import ModuleCoordinator
from amplifier_core.events import TOOL_POST

logger = logging.getLogger(__name__)


class LinterHook:
    """Linterフック"""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - linters: ファイル拡張子ごとのlinterコマンド
                - auto_fix: 自動修正を試行（デフォルト: False）
        """
        self._linters = config.get("linters", {
            ".py": "ruff check",
            ".js": "eslint",
            ".ts": "eslint",
        })

        self._auto_fix = config.get("auto_fix", False)

    async def handle_tool_post(self, event: str, data: dict) -> HookResult:
        """ツール実行後のLintチェック"""
        tool = data.get("tool")
        arguments = data.get("arguments", {})
        result = data.get("result", {})

        # ファイル書き込み操作のみ
        if tool != "filesystem" or arguments.get("operation") != "write":
            return HookResult(action="continue")

        if not result.get("success"):
            return HookResult(action="continue")

        # ファイルパスとLinterの取得
        path = arguments.get("path", "")
        linter_cmd = self._get_linter_for_file(path)

        if not linter_cmd:
            return HookResult(action="continue")

        logger.info(f"Running linter on {path}: {linter_cmd}")

        # Linter実行
        errors = await self._run_linter(linter_cmd, path)

        if not errors:
            return HookResult(
                action="continue",
                user_message=f"✓ Linting passed for {path}",
                user_message_level="info"
            )

        # エラーがある場合、コンテキストに注入
        error_message = f"Linter found {len(errors)} issue(s) in {path}:\n"
        error_message += "\n".join(f"  - {err}" for err in errors)

        return HookResult(
            action="inject_context",
            context_injection=error_message,
            context_injection_role="system",
            user_message=f"⚠️  Found {len(errors)} linting issues in {path}",
            user_message_level="warning",
            ephemeral=False  # 永続的に保存してエージェントが修正できるようにする
        )

    def _get_linter_for_file(self, path: str) -> str | None:
        """ファイルの拡張子からLinterを取得"""
        for ext, linter in self._linters.items():
            if path.endswith(ext):
                return linter
        return None

    async def _run_linter(self, linter_cmd: str, path: str) -> list[str]:
        """Linterを実行してエラーを取得"""
        try:
            process = await asyncio.create_subprocess_shell(
                f"{linter_cmd} {path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            # エラー出力をパース
            output = stdout.decode() + stderr.decode()
            errors = [line.strip() for line in output.split("\n") if line.strip()]

            return errors[:10]  # 最大10件

        except Exception as e:
            logger.error(f"Linter execution failed: {e}")
            return []


async def mount(coordinator: ModuleCoordinator, config: dict):
    """Linter Hookをマウント"""
    logger.info("Mounting Linter hook")

    hook = LinterHook(config)

    # ツール実行後イベントに登録
    coordinator.hooks.register(
        TOOL_POST,
        hook.handle_tool_post,
        priority=10,
        name="linter-hook"
    )

    logger.info("Linter hook mounted successfully")

    return None
```

## 実装例4: メトリクスフック

```python
"""
Metrics Hook モジュール

メトリクスを収集し、セッション終了時に表示するフックです。
"""

import logging
from datetime import datetime
from typing import Any

from amplifier_core import HookResult
from amplifier_core.coordinator import ModuleCoordinator
from amplifier_core.events import (
    SESSION_START, SESSION_END,
    PROVIDER_RESPONSE, TOOL_POST
)

logger = logging.getLogger(__name__)


class MetricsHook:
    """メトリクス収集フック"""

    def __init__(self, config: dict[str, Any]):
        self._start_time = None

        # メトリクス
        self._provider_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._tool_executions = 0
        self._tool_successes = 0
        self._tool_failures = 0

    async def handle_session_start(self, event: str, data: dict) -> HookResult:
        """セッション開始"""
        self._start_time = datetime.now()
        logger.info("Metrics collection started")
        return HookResult(action="continue")

    async def handle_provider_response(self, event: str, data: dict) -> HookResult:
        """プロバイダーレスポンス"""
        self._provider_calls += 1

        usage = data.get("usage", {})
        self._total_input_tokens += usage.get("input_tokens", 0)
        self._total_output_tokens += usage.get("output_tokens", 0)

        return HookResult(action="continue")

    async def handle_tool_post(self, event: str, data: dict) -> HookResult:
        """ツール実行後"""
        self._tool_executions += 1

        result = data.get("result", {})
        if result.get("success"):
            self._tool_successes += 1
        else:
            self._tool_failures += 1

        return HookResult(action="continue")

    async def handle_session_end(self, event: str, data: dict) -> HookResult:
        """セッション終了"""
        duration = (datetime.now() - self._start_time).total_seconds()

        # メトリクスサマリーを作成
        summary = f"""
Session Metrics:
  Duration: {duration:.2f}s
  Provider Calls: {self._provider_calls}
  Total Tokens: {self._total_input_tokens + self._total_output_tokens}
    - Input: {self._total_input_tokens}
    - Output: {self._total_output_tokens}
  Tool Executions: {self._tool_executions}
    - Successes: {self._tool_successes}
    - Failures: {self._tool_failures}
"""

        logger.info(summary)

        # ユーザーに表示
        return HookResult(
            action="continue",
            user_message=summary.strip(),
            user_message_level="info"
        )


async def mount(coordinator: ModuleCoordinator, config: dict):
    """Metrics Hookをマウント"""
    logger.info("Mounting Metrics hook")

    hook = MetricsHook(config)

    # 各イベントに登録
    coordinator.hooks.register(SESSION_START, hook.handle_session_start, name="metrics")
    coordinator.hooks.register(PROVIDER_RESPONSE, hook.handle_provider_response, name="metrics")
    coordinator.hooks.register(TOOL_POST, hook.handle_tool_post, name="metrics")
    coordinator.hooks.register(SESSION_END, hook.handle_session_end, name="metrics")

    logger.info("Metrics hook mounted successfully")

    return None
```

## 使用例

```python
config = {
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple"
    },
    "providers": [...],
    "tools": [...],
    "hooks": [
        {
            "module": "hook-logging",
            "config": {
                "log_file": "./logs/events.jsonl",
                "log_level": "INFO"
            }
        },
        {
            "module": "hook-security",
            "config": {
                "protected_paths": ["/production", "/etc"],
                "require_approval": ["production", "database"]
            }
        },
        {
            "module": "hook-linter",
            "config": {
                "linters": {
                    ".py": "ruff check",
                    ".js": "eslint"
                }
            }
        },
        {
            "module": "hook-metrics",
            "config": {}
        }
    ]
}

session = AmplifierSession(config)
await session.initialize()

result = await session.execute("Write a Python script to hello.py")
# → Linterが実行され、エラーがあればコンテキストに注入される
# → エージェントがエラーを見て自動修正を試みる
```

## エントリーポイント設定

**pyproject.toml:**

```toml
[project.entry-points."amplifier.modules"]
hook-logging = "amplifier_module_hook_logging:mount"
hook-security = "amplifier_module_hook_security:mount"
hook-linter = "amplifier_module_hook_linter:mount"
hook-metrics = "amplifier_module_hook_metrics:mount"
```

## まとめ

Hookモジュールは以下の用途に使用できます：

1. **観測性**: ロギング、メトリクス収集、監査
2. **セキュリティ**: 危険な操作のブロック、承認ゲート
3. **品質保証**: Linting、テスト実行、自動フィードバック
4. **ワークフロー制御**: 条件分岐、状態管理、通知

フックシステムの柔軟性により、カーネルを変更せずにシステムの動作をカスタマイズできます。
