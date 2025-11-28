# 08. CLIエージェント統合 - ファイル編集とコマンド実行の管理

このガイドでは、Claude CodeのようなCLIエージェントが、実際にファイルを編集したりコマンドを実行したりする機能がAmplifier Coreでどのように管理されるかを解説します。

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────┐
│ CLIアプリケーション層 (amplifier-app-cli)                    │
│ ・ユーザーインターフェース                                   │
│ ・ApprovalSystem実装（ユーザー承認UI）                      │
│ ・DisplaySystem実装（出力表示）                              │
└──────────────────┬──────────────────────────────────────────┘
                   │ セッション作成、設定注入
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ Amplifier Core カーネル                                      │
│ ・セッション管理 (session.py)                                │
│ ・コーディネーター (coordinator.py)                          │
│ ・フックシステム (hooks.py)                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │ ツール呼び出し、フック発火
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ モジュール層                                                 │
│ ・Toolモジュール (tool-bash, tool-filesystem, tool-edit)    │
│ ・Hookモジュール (hook-security, hook-approval)              │
└─────────────────────────────────────────────────────────────┘
                   │
                   ↓
              実際のシステム
         (ファイルシステム、シェル)
```

## 1. ツールモジュールによる実行管理

### 1-1. Bash Tool - コマンド実行

**実装:** [tool-example.md - Bash Tool](../module-examples/tool-example.md#実装例1-bash-tool)

**重要な機能:**

```python
class BashTool:
    """シェルコマンド実行ツール"""

    def __init__(self, config):
        # 設定による制約
        self._timeout = config.get("timeout", 30)  # タイムアウト
        self._allowed_commands = config.get("allowed_commands")  # 許可コマンド
        self._working_directory = config.get("working_directory", ".")

    async def execute(self, input: dict) -> ToolResult:
        command = input.get("command")

        # 1. コマンド検証
        if self._allowed_commands:
            cmd_name = command.split()[0]
            if cmd_name not in self._allowed_commands:
                return ToolResult(
                    success=False,
                    error={"message": f"Command '{cmd_name}' is not allowed"}
                )

        # 2. コマンド実行
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._working_directory
        )

        # 3. タイムアウト付き待機
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self._timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            return ToolResult(success=False, error={"message": "Timeout"})

        # 4. 結果を返す
        output = stdout.decode("utf-8", errors="replace")
        if stderr:
            output += "\n[stderr]\n" + stderr.decode("utf-8", errors="replace")

        return ToolResult(success=True, output=output)
```

**使用例:**

```python
config = {
    "tools": [
        {
            "module": "tool-bash",
            "config": {
                "timeout": 60,
                "allowed_commands": ["ls", "cat", "grep", "git", "npm", "pytest"],
                "working_directory": "/home/user/project"
            }
        }
    ]
}
```

---

### 1-2. Filesystem Tool - ファイル操作

**実装:** [tool-example.md - Filesystem Tool](../module-examples/tool-example.md#実装例2-filesystem-tool)

**重要な機能:**

```python
class FilesystemTool:
    """ファイルシステム操作ツール"""

    def __init__(self, config):
        # パス制約
        self._allowed_paths = [
            Path(p).resolve() for p in config.get("allowed_paths", ["."])
        ]
        self._max_file_size = config.get("max_file_size", 1024 * 1024)

    async def execute(self, input: dict) -> ToolResult:
        operation = input.get("operation")  # "read", "write", "list"
        path = Path(input.get("path")).resolve()

        # 1. パス検証
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                error={"message": f"Access to path '{path}' is not allowed"}
            )

        # 2. 操作実行
        if operation == "read":
            return await self._read_file(path)
        elif operation == "write":
            return await self._write_file(path, input.get("content", ""))
        elif operation == "list":
            return await self._list_directory(path)

    def _is_path_allowed(self, path: Path) -> bool:
        """パスが許可されているかチェック"""
        for allowed in self._allowed_paths:
            try:
                path.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False
```

**使用例:**

```python
config = {
    "tools": [
        {
            "module": "tool-filesystem",
            "config": {
                "allowed_paths": [
                    "/home/user/project",
                    "/tmp"
                ],
                "max_file_size": 5242880  # 5MB
            }
        }
    ]
}
```

---

### 1-3. Edit Tool - ファイル編集（Claude Code風）

**新規実装例:**

```python
"""
Edit Tool モジュール

Claude Code風のファイル編集ツールです。
検索と置換によるファイル編集を提供します。
"""

import logging
from pathlib import Path
from typing import Any

from amplifier_core import ToolResult
from amplifier_core.coordinator import ModuleCoordinator

logger = logging.getLogger(__name__)


class EditTool:
    """ファイル編集ツール"""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - allowed_paths: 編集可能なパスのリスト
                - backup: 編集前にバックアップを作成（デフォルト: True）
        """
        self.name = "edit"
        self.description = (
            "Edit files by searching and replacing text. "
            "Use this to make precise changes to existing files."
        )

        self._allowed_paths = [
            Path(p).resolve() for p in config.get("allowed_paths", ["."])
        ]
        self._backup = config.get("backup", True)

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """
        ファイル編集を実行。

        Args:
            input: 入力パラメータ
                - path: ファイルパス
                - old_string: 検索する文字列
                - new_string: 置換する文字列
                - replace_all: すべての出現を置換（デフォルト: False）

        Returns:
            ToolResult
        """
        path_str = input.get("path")
        old_string = input.get("old_string")
        new_string = input.get("new_string")
        replace_all = input.get("replace_all", False)

        if not all([path_str, old_string is not None, new_string is not None]):
            return ToolResult(
                success=False,
                error={"message": "path, old_string, and new_string are required"}
            )

        path = Path(path_str).resolve()

        # パス検証
        if not self._is_path_allowed(path):
            return ToolResult(
                success=False,
                error={"message": f"Access to path '{path}' is not allowed"}
            )

        if not path.is_file():
            return ToolResult(
                success=False,
                error={"message": f"File not found: {path}"}
            )

        try:
            # ファイル読み込み
            original_content = path.read_text(encoding="utf-8")

            # 検索
            if old_string not in original_content:
                return ToolResult(
                    success=False,
                    error={"message": f"String not found in file: {old_string}"}
                )

            # ユニーク性チェック（replace_all=Falseの場合）
            if not replace_all and original_content.count(old_string) > 1:
                return ToolResult(
                    success=False,
                    error={
                        "message": f"String appears {original_content.count(old_string)} times. "
                                   f"Use replace_all=true or provide a more specific string."
                    }
                )

            # バックアップ作成
            if self._backup:
                backup_path = path.with_suffix(path.suffix + ".bak")
                backup_path.write_text(original_content, encoding="utf-8")

            # 置換
            if replace_all:
                new_content = original_content.replace(old_string, new_string)
                replacements = original_content.count(old_string)
            else:
                new_content = original_content.replace(old_string, new_string, 1)
                replacements = 1

            # 書き込み
            path.write_text(new_content, encoding="utf-8")

            logger.info(f"Edited file: {path} ({replacements} replacements)")

            return ToolResult(
                success=True,
                output={
                    "path": str(path),
                    "replacements": replacements,
                    "backup": str(backup_path) if self._backup else None
                }
            )

        except Exception as e:
            logger.error(f"Edit failed: {e}")
            return ToolResult(
                success=False,
                error={"message": str(e), "type": type(e).__name__}
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

    def get_tool_spec(self) -> dict:
        """LLMに渡すツール仕様を生成"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to edit"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to search for"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The string to replace it with"
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences (default: false)",
                        "default": False
                    }
                },
                "required": ["path", "old_string", "new_string"]
            }
        }


async def mount(coordinator: ModuleCoordinator, config: dict):
    """Edit Toolをマウント"""
    logger.info("Mounting Edit tool")

    tool = EditTool(config)
    await coordinator.mount("tools", tool, name="edit")

    logger.info("Edit tool mounted successfully")
    return None
```

---

## 2. セキュリティフックによる制御

**実装:** [hook-example.md - Security Hook](../module-examples/hook-example.md#実装例2-セキュリティフック)

### 2-1. 危険な操作のブロック

```python
class SecurityHook:
    """セキュリティフック"""

    def __init__(self, config):
        # 危険なコマンドパターン
        self._blocked_commands = config.get("blocked_commands", [
            r"rm\s+-rf\s+/",      # ルートディレクトリの削除
            r":(){ :|:& };:",      # Fork bomb
            r"mkfs",               # ファイルシステム作成
            r"dd\s+if=.*of=/dev/", # デバイスへの直接書き込み
        ])

        # 保護されたパス
        self._protected_paths = config.get("protected_paths", [
            "/etc",
            "/sys",
            "/proc",
            "/boot"
        ])

    async def handle_tool_pre(self, event: str, data: dict) -> HookResult:
        """ツール実行前のセキュリティチェック"""
        tool = data.get("tool")
        arguments = data.get("arguments", {})

        # Bashコマンドのチェック
        if tool == "bash":
            command = arguments.get("command", "")

            # 危険なコマンドパターンをチェック
            for pattern in self._blocked_commands:
                if re.search(pattern, command):
                    logger.warning(f"Blocked dangerous command: {command}")
                    return HookResult(
                        action="deny",
                        reason=f"Command matches blocked pattern: {pattern}",
                        user_message=f"⚠️  Blocked dangerous command: {command}",
                        user_message_level="error"
                    )

        # ファイルシステム操作のチェック
        if tool in ["filesystem", "edit"]:
            operation = arguments.get("operation")
            path = arguments.get("path", "")

            # 保護されたパスへの書き込みをブロック
            if operation in ["write"] or tool == "edit":
                for protected in self._protected_paths:
                    if path.startswith(protected):
                        logger.warning(f"Blocked write to protected path: {path}")
                        return HookResult(
                            action="deny",
                            reason=f"Write to protected path: {protected}",
                            user_message=f"⚠️  Cannot modify protected path: {path}",
                            user_message_level="error"
                        )

        return HookResult(action="continue")
```

**使用例:**

```python
config = {
    "hooks": [
        {
            "module": "hook-security",
            "config": {
                "blocked_commands": [
                    r"rm\s+-rf\s+/",
                    r"curl.*\|.*sh",  # パイプ経由の実行をブロック
                    r"wget.*-O.*\|"
                ],
                "protected_paths": [
                    "/etc",
                    "/production",
                    "/home/user/.ssh"
                ]
            }
        }
    ]
}
```

---

### 2-2. 動的な承認ゲート

```python
class ApprovalHook:
    """承認が必要な操作をチェックするフック"""

    def __init__(self, config):
        # 承認が必要なパターン
        self._require_approval = config.get("require_approval", {
            "paths": ["production", "config", "database"],
            "commands": ["git push", "npm publish", "docker push"]
        })

    async def handle_tool_pre(self, event: str, data: dict) -> HookResult:
        """ツール実行前の承認チェック"""
        tool = data.get("tool")
        arguments = data.get("arguments", {})

        # ファイル編集の承認
        if tool in ["edit", "filesystem"]:
            path = arguments.get("path", "")

            for keyword in self._require_approval["paths"]:
                if keyword in path.lower():
                    return HookResult(
                        action="ask_user",
                        approval_prompt=f"Allow editing {path}?",
                        approval_options=["Allow once", "Allow always", "Deny"],
                        approval_timeout=300.0,
                        approval_default="deny",
                        user_message=f"🔒 Approval required for: {path}",
                        user_message_level="warning"
                    )

        # コマンド実行の承認
        if tool == "bash":
            command = arguments.get("command", "")

            for pattern in self._require_approval["commands"]:
                if pattern in command:
                    return HookResult(
                        action="ask_user",
                        approval_prompt=f"Allow running: {command}?",
                        approval_options=["Allow once", "Deny"],
                        approval_timeout=60.0,
                        approval_default="deny",
                        user_message=f"🔒 Approval required for command",
                        user_message_level="warning"
                    )

        return HookResult(action="continue")
```

---

## 3. ApprovalSystemの実装（アプリ層）

ApprovalSystemはアプリケーション層が実装する必要があります。

**インターフェース:** `approval.py`

```python
from typing import Protocol

class ApprovalSystem(Protocol):
    """承認システムのプロトコル"""

    async def request_approval(
        self,
        prompt: str,
        options: list[str],
        timeout: float | None = None,
        default: str | None = None
    ) -> str:
        """
        ユーザーに承認を要求。

        Args:
            prompt: 承認リクエストメッセージ
            options: 選択肢のリスト
            timeout: タイムアウト秒数
            default: タイムアウト時のデフォルト選択

        Returns:
            選択されたオプション

        Raises:
            ApprovalTimeoutError: タイムアウト時
        """
        ...
```

### 3-1. CLI用の実装例

```python
"""
CLI Approval System

ターミナルでユーザーに承認を求めるシステムです。
"""

import asyncio
from typing import List

from amplifier_core.approval import ApprovalSystem, ApprovalTimeoutError


class CLIApprovalSystem(ApprovalSystem):
    """CLI用の承認システム"""

    def __init__(self):
        self._approval_cache = {}  # "Allow always"のキャッシュ

    async def request_approval(
        self,
        prompt: str,
        options: list[str],
        timeout: float | None = None,
        default: str | None = None
    ) -> str:
        """ユーザーに承認を要求"""

        # キャッシュチェック
        cache_key = prompt
        if cache_key in self._approval_cache:
            cached_decision = self._approval_cache[cache_key]
            print(f"[Cached] {prompt} → {cached_decision}")
            return cached_decision

        # プロンプト表示
        print(f"\n{'='*60}")
        print(f"⚠️  APPROVAL REQUIRED")
        print(f"{'='*60}")
        print(f"\n{prompt}\n")

        # 選択肢表示
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")

        print(f"\nTimeout: {timeout}s (default: {default})" if timeout else "")

        # ユーザー入力を非同期で取得
        try:
            if timeout:
                decision = await asyncio.wait_for(
                    self._get_user_input(options),
                    timeout=timeout
                )
            else:
                decision = await self._get_user_input(options)

            # "Allow always"の場合はキャッシュ
            if decision == "Allow always":
                self._approval_cache[cache_key] = "Allow once"
                decision = "Allow once"  # 実際の動作は"Allow once"と同じ

            print(f"{'='*60}\n")
            return decision

        except asyncio.TimeoutError:
            print(f"\n⏱️  Timeout! Using default: {default}\n")
            print(f"{'='*60}\n")

            if default == "deny":
                raise ApprovalTimeoutError(f"Approval timeout for: {prompt}")

            return default or options[0]

    async def _get_user_input(self, options: list[str]) -> str:
        """ユーザー入力を取得"""
        while True:
            # asyncioのrun_in_executorで標準入力を非同期化
            loop = asyncio.get_event_loop()
            user_input = await loop.run_in_executor(
                None,
                input,
                "\nYour choice (1-{} or option name): ".format(len(options))
            )

            user_input = user_input.strip()

            # 数字での選択
            if user_input.isdigit():
                choice_idx = int(user_input) - 1
                if 0 <= choice_idx < len(options):
                    return options[choice_idx]

            # 名前での選択
            if user_input in options:
                return user_input

            print("❌ Invalid choice. Please try again.")
```

### 3-2. 使用例

```python
async def main():
    # ApprovalSystemの作成
    approval_system = CLIApprovalSystem()
    display_system = CLIDisplaySystem()

    # Sessionに注入
    session = AmplifierSession(
        config=config,
        approval_system=approval_system,
        display_system=display_system
    )

    await session.initialize()

    # 実行
    result = await session.execute(
        "Edit the production/config.py file to change the API endpoint"
    )
```

**実行時の出力:**

```
============================================================
⚠️  APPROVAL REQUIRED
============================================================

Allow editing production/config.py?

  1. Allow once
  2. Allow always
  3. Deny

Timeout: 300.0s (default: deny)

Your choice (1-3 or option name): 1
============================================================

✓ Editing production/config.py...
```

---

## 4. 完全なCLIエージェント設定例

```python
"""
complete_cli_agent.py

Claude Code風のCLIエージェントの完全な実装例です。
"""

import asyncio
from amplifier_core import AmplifierSession


async def main():
    # 設定
    config = {
        "session": {
            "orchestrator": "loop-basic",
            "context": {
                "module": "context-persistent",
                "config": {
                    "storage_path": "./agent_sessions",
                    "max_messages": 200
                }
            }
        },
        "providers": [
            {
                "module": "provider-anthropic",
                "config": {
                    "api_key": "your-api-key",
                    "default_model": "claude-sonnet-4-5-20250929"
                }
            }
        ],
        "tools": [
            {
                "module": "tool-bash",
                "config": {
                    "timeout": 120,
                    "allowed_commands": [
                        "ls", "cat", "grep", "find", "head", "tail",
                        "git", "npm", "python", "pytest", "ruff"
                    ],
                    "working_directory": "/home/user/project"
                }
            },
            {
                "module": "tool-filesystem",
                "config": {
                    "allowed_paths": ["/home/user/project"],
                    "max_file_size": 10485760  # 10MB
                }
            },
            {
                "module": "tool-edit",
                "config": {
                    "allowed_paths": ["/home/user/project"],
                    "backup": True
                }
            }
        ],
        "hooks": [
            {
                "module": "hook-security",
                "config": {
                    "blocked_commands": [
                        r"rm\s+-rf\s+/",
                        r":(){ :|:& };:",
                        r"curl.*\|.*sh"
                    ],
                    "protected_paths": [
                        "/etc",
                        "/home/user/.ssh",
                        "/home/user/project/production"
                    ]
                }
            },
            {
                "module": "hook-approval",
                "config": {
                    "require_approval": {
                        "paths": ["production", "config", ".env"],
                        "commands": ["git push", "npm publish", "rm -rf"]
                    }
                }
            },
            {
                "module": "hook-linter",
                "config": {
                    "linters": {
                        ".py": "ruff check",
                        ".js": "eslint",
                        ".ts": "eslint"
                    },
                    "auto_fix": False
                }
            },
            {
                "module": "hook-logger",
                "config": {
                    "log_file": "./agent.log",
                    "log_level": "INFO"
                }
            }
        ]
    }

    # ApprovalSystemとDisplaySystemの作成
    approval_system = CLIApprovalSystem()
    display_system = CLIDisplaySystem()

    # Sessionの作成
    session = AmplifierSession(
        config=config,
        approval_system=approval_system,
        display_system=display_system
    )

    await session.initialize()

    # メインループ
    print("CLI Agent started. Type 'exit' to quit.")

    while True:
        try:
            # ユーザー入力
            prompt = input("\n> ")

            if prompt.strip().lower() == "exit":
                break

            # 実行
            result = await session.execute(prompt)

            # 結果表示
            print(f"\n{result}\n")

        except KeyboardInterrupt:
            print("\n\nExiting...")
            break

        except Exception as e:
            print(f"\n❌ Error: {e}\n")

    # クリーンアップ
    await session.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 5. 実行フロー - ファイル編集の例

**ユーザープロンプト:** "Edit config/settings.py to change DEBUG=True to DEBUG=False"

### フロー1: ツール呼び出しの決定

```
1. Orchestrator
   └─ provider.complete(ChatRequest(...))
       ↓
   Anthropic APIがツール呼び出しを返す:
   ToolCall(
       tool="edit",
       arguments={
           "path": "config/settings.py",
           "old_string": "DEBUG=True",
           "new_string": "DEBUG=False"
       }
   )
```

### フロー2: セキュリティフックの実行

```
2. hooks.emit(TOOL_PRE, {
       "tool": "edit",
       "arguments": {"path": "config/settings.py", ...}
   })
   ↓
   SecurityHook.handle_tool_pre()
   ├─ パスチェック: "config" は保護パスか？
   │  └─ No → continue
   └─ return HookResult(action="continue")
```

### フロー3: 承認フックの実行

```
3. ApprovalHook.handle_tool_pre()
   ├─ パスチェック: "config" は承認が必要か？
   │  └─ Yes → 承認リクエスト
   │
   └─ return HookResult(
          action="ask_user",
          approval_prompt="Allow editing config/settings.py?",
          approval_options=["Allow once", "Allow always", "Deny"]
      )
```

### フロー4: 承認処理

```
4. coordinator.process_hook_result(hook_result, ...)
   └─ _handle_approval_request()
       ↓
       approval_system.request_approval(
           prompt="Allow editing config/settings.py?",
           options=["Allow once", "Allow always", "Deny"],
           timeout=300.0
       )
       ↓
   ┌─────────────────────────────────────┐
   │ CLI表示:                             │
   │ ⚠️  APPROVAL REQUIRED                │
   │                                      │
   │ Allow editing config/settings.py?   │
   │                                      │
   │   1. Allow once                     │
   │   2. Allow always                   │
   │   3. Deny                           │
   │                                      │
   │ Your choice: 1                      │
   └─────────────────────────────────────┘
       ↓
       ユーザーが "1" を選択
       ↓
       return HookResult(action="continue")
```

### フロー5: ツール実行

```
5. tool.execute({"path": "config/settings.py", ...})
   ↓
   EditTool.execute()
   ├─ パス検証
   ├─ ファイル読み込み
   ├─ "DEBUG=True" を検索
   ├─ ユニーク性チェック
   ├─ バックアップ作成: config/settings.py.bak
   ├─ "DEBUG=True" → "DEBUG=False" に置換
   ├─ ファイル書き込み
   └─ return ToolResult(success=True, output={...})
```

### フロー6: ツール実行後イベント

```
6. hooks.emit(TOOL_POST, {
       "tool": "edit",
       "result": {"success": True, "replacements": 1}
   })
   ↓
   LinterHook.handle_tool_post()
   ├─ ruff check config/settings.py を実行
   ├─ エラーなし
   └─ return HookResult(
          action="continue",
          user_message="✓ Linting passed for config/settings.py"
      )
```

### フロー7: 結果の表示

```
7. display_system.show_message(
       message="✓ Linting passed for config/settings.py",
       level="info"
   )
   ↓
   ターミナルに出力:
   ✓ Linting passed for config/settings.py
```

---

## 6. セキュリティのベストプラクティス

### 6-1. 多層防御

```
Layer 1: ツール設定による制限
├─ allowed_commands
├─ allowed_paths
├─ timeout
└─ max_file_size

Layer 2: セキュリティフックによるブロック
├─ 危険なパターンマッチング
├─ 保護パスのチェック
└─ deny で即座にブロック

Layer 3: 承認フックによる動的承認
├─ 重要な操作の承認リクエスト
├─ ユーザーの明示的な許可
└─ タイムアウトとデフォルト動作

Layer 4: 実行後のバリデーション
├─ Linterによるチェック
├─ テスト実行
└─ 結果の検証
```

### 6-2. 設定例

```python
# セキュアな本番環境設定
config = {
    "tools": [
        {
            "module": "tool-bash",
            "config": {
                "timeout": 30,
                "allowed_commands": [
                    "ls", "cat", "grep",  # 読み取りのみ
                ],
                "working_directory": "/app/readonly"
            }
        },
        {
            "module": "tool-edit",
            "config": {
                "allowed_paths": ["/app/src"],  # ソースコードのみ
                "backup": True
            }
        }
    ],
    "hooks": [
        {
            "module": "hook-security",
            "config": {
                "blocked_commands": [
                    r"rm", r"mv", r"curl", r"wget"  # 厳しい制限
                ],
                "protected_paths": [
                    "/app/production",
                    "/app/config",
                    "/app/.env"
                ]
            }
        },
        {
            "module": "hook-approval",
            "config": {
                "require_approval": {
                    "paths": ["*"],  # すべてのファイル編集に承認が必要
                    "commands": ["*"]  # すべてのコマンドに承認が必要
                }
            }
        }
    ]
}
```

---

## まとめ

CLIエージェントでファイル編集やコマンド実行を安全に管理するには：

1. **Toolモジュール** - 設定による制限（パス、コマンド、タイムアウト）
2. **Securityフック** - 危険な操作の自動ブロック
3. **Approvalフック** - 重要な操作の動的承認
4. **ApprovalSystem** - アプリ層でのユーザーインタラクション
5. **Linterフック** - 実行後の検証と自動フィードバック

これらの層が協調して、安全で柔軟なエージェントシステムを実現します。

## 次のステップ

- [tool-example.md](../module-examples/tool-example.md)で実際のツール実装を確認
- [hook-example.md](../module-examples/hook-example.md)でセキュリティフックの実装を確認
- [04-hook-system.md](./04-hook-system.md)でフック結果処理の詳細を理解
