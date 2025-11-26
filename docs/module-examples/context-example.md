# Context Manager実装例

Context Managerは会話履歴（コンテキスト）を管理するモジュールです。

## ContextManagerプロトコル

**定義:** `interfaces.py:125-147`

```python
@runtime_checkable
class ContextManager(Protocol):
    async def add_message(self, message: dict[str, Any]) -> None:
        """メッセージをコンテキストに追加"""
        ...

    async def get_messages(self) -> list[dict[str, Any]]:
        """すべてのメッセージを取得"""
        ...

    async def should_compact(self) -> bool:
        """コンパクションが必要かチェック"""
        ...

    async def compact(self) -> None:
        """コンテキストを圧縮"""
        ...

    async def clear(self) -> None:
        """すべてのメッセージをクリア"""
        ...
```

## 実装例1: Simple Context Manager

```python
"""
Simple Context Manager モジュール

シンプルなインメモリコンテキストマネージャーです。
"""

import logging
from typing import Any

from amplifier_core.coordinator import ModuleCoordinator

logger = logging.getLogger(__name__)


class SimpleContextManager:
    """シンプルなインメモリコンテキストマネージャー"""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - max_messages: 最大メッセージ数（デフォルト: 100）
                - max_tokens: 最大トークン数（デフォルト: 8000）
                - compact_to_messages: コンパクション後のメッセージ数（デフォルト: 50）
        """
        self._max_messages = config.get("max_messages", 100)
        self._max_tokens = config.get("max_tokens", 8000)
        self._compact_to_messages = config.get("compact_to_messages", 50)

        self._messages = []
        self._total_tokens = 0

    async def add_message(self, message: dict[str, Any]) -> None:
        """メッセージをコンテキストに追加"""
        self._messages.append(message)

        # トークン数の概算（1トークン ≈ 4文字）
        content = message.get("content", "")
        if isinstance(content, str):
            tokens = len(content) // 4
        else:
            tokens = 0

        self._total_tokens += tokens

        logger.debug(f"Added message: role={message.get('role')}, tokens≈{tokens}")

    async def get_messages(self) -> list[dict[str, Any]]:
        """すべてのメッセージを取得"""
        return self._messages.copy()

    async def should_compact(self) -> bool:
        """コンパクションが必要かチェック"""
        if len(self._messages) >= self._max_messages:
            logger.info(f"Context has {len(self._messages)} messages (max: {self._max_messages})")
            return True

        if self._total_tokens >= self._max_tokens:
            logger.info(f"Context has ~{self._total_tokens} tokens (max: {self._max_tokens})")
            return True

        return False

    async def compact(self) -> None:
        """
        コンテキストを圧縮。

        戦略: 古いメッセージを削除し、最新のN件を保持
        """
        if len(self._messages) <= self._compact_to_messages:
            logger.info("Context already below compact threshold")
            return

        # 最新のN件を保持
        old_count = len(self._messages)
        self._messages = self._messages[-self._compact_to_messages:]

        # トークン数を再計算
        self._total_tokens = sum(
            len(msg.get("content", "")) // 4
            for msg in self._messages
            if isinstance(msg.get("content"), str)
        )

        logger.info(
            f"Compacted context: {old_count} → {len(self._messages)} messages, "
            f"~{self._total_tokens} tokens"
        )

    async def clear(self) -> None:
        """すべてのメッセージをクリア"""
        self._messages.clear()
        self._total_tokens = 0
        logger.info("Cleared all messages")


async def mount(coordinator: ModuleCoordinator, config: dict):
    """Simple Context Managerをマウント"""
    logger.info("Mounting Simple Context Manager")

    context = SimpleContextManager(config)

    await coordinator.mount("context", context)

    logger.info("Simple Context Manager mounted successfully")

    return None
```

## 実装例2: Persistent Context Manager

```python
"""
Persistent Context Manager モジュール

ファイルに永続化するコンテキストマネージャーです。
"""

import json
import logging
from pathlib import Path
from typing import Any

from amplifier_core.coordinator import ModuleCoordinator

logger = logging.getLogger(__name__)


class PersistentContextManager:
    """ファイル永続化コンテキストマネージャー"""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - storage_path: 保存先ディレクトリ（必須）
                - max_messages: 最大メッセージ数（デフォルト: 200）
                - max_tokens: 最大トークン数（デフォルト: 10000）
                - auto_save: 自動保存有効化（デフォルト: True）
        """
        storage_path = config.get("storage_path")
        if not storage_path:
            raise ValueError("storage_path is required")

        self._storage_dir = Path(storage_path)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self._max_messages = config.get("max_messages", 200)
        self._max_tokens = config.get("max_tokens", 10000)
        self._auto_save = config.get("auto_save", True)

        # セッションIDはマウント時にCoordinatorから取得
        self._session_id = None
        self._messages = []
        self._total_tokens = 0

    def _get_storage_file(self) -> Path:
        """保存ファイルパスを取得"""
        return self._storage_dir / f"{self._session_id}.jsonl"

    async def load(self, session_id: str) -> None:
        """セッションのコンテキストをロード"""
        self._session_id = session_id
        storage_file = self._get_storage_file()

        if storage_file.exists():
            logger.info(f"Loading context from {storage_file}")

            with storage_file.open("r") as f:
                for line in f:
                    message = json.loads(line)
                    self._messages.append(message)

            self._recalculate_tokens()

            logger.info(f"Loaded {len(self._messages)} messages")
        else:
            logger.info(f"No existing context found for session {session_id}")

    async def save(self) -> None:
        """コンテキストを保存"""
        storage_file = self._get_storage_file()

        logger.debug(f"Saving context to {storage_file}")

        with storage_file.open("w") as f:
            for message in self._messages:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")

        logger.debug(f"Saved {len(self._messages)} messages")

    async def add_message(self, message: dict[str, Any]) -> None:
        """メッセージをコンテキストに追加"""
        self._messages.append(message)

        # トークン数の概算
        content = message.get("content", "")
        if isinstance(content, str):
            tokens = len(content) // 4
        else:
            tokens = 0

        self._total_tokens += tokens

        # 自動保存
        if self._auto_save:
            await self.save()

        logger.debug(f"Added message: role={message.get('role')}, tokens≈{tokens}")

    async def get_messages(self) -> list[dict[str, Any]]:
        """すべてのメッセージを取得"""
        return self._messages.copy()

    async def should_compact(self) -> bool:
        """コンパクションが必要かチェック"""
        return (
            len(self._messages) >= self._max_messages
            or self._total_tokens >= self._max_tokens
        )

    async def compact(self) -> None:
        """
        コンテキストを圧縮。

        戦略: 要約を使用
        """
        if len(self._messages) < 20:
            logger.info("Context too small to compact")
            return

        old_count = len(self._messages)

        # システムメッセージと最新の10件を保持
        system_messages = [m for m in self._messages if m.get("role") == "system"]
        recent_messages = self._messages[-10:]

        # 中間部分を要約（簡略化: 実際にはLLMを使用して要約）
        summary = {
            "role": "system",
            "content": f"[Previous conversation summary: {old_count - 10} messages]",
            "metadata": {
                "type": "summary",
                "original_count": old_count - 10
            }
        }

        # 新しいメッセージリストを構築
        self._messages = system_messages + [summary] + recent_messages

        self._recalculate_tokens()

        # 保存
        await self.save()

        logger.info(
            f"Compacted context: {old_count} → {len(self._messages)} messages, "
            f"~{self._total_tokens} tokens"
        )

    async def clear(self) -> None:
        """すべてのメッセージをクリア"""
        self._messages.clear()
        self._total_tokens = 0

        # ファイルも削除
        storage_file = self._get_storage_file()
        if storage_file.exists():
            storage_file.unlink()

        logger.info("Cleared all messages and deleted storage file")

    def _recalculate_tokens(self) -> None:
        """トークン数を再計算"""
        self._total_tokens = sum(
            len(msg.get("content", "")) // 4
            for msg in self._messages
            if isinstance(msg.get("content"), str)
        )


async def mount(coordinator: ModuleCoordinator, config: dict):
    """Persistent Context Managerをマウント"""
    logger.info("Mounting Persistent Context Manager")

    context = PersistentContextManager(config)

    # セッションIDを取得してロード
    session_id = coordinator.session_id
    await context.load(session_id)

    await coordinator.mount("context", context)

    logger.info("Persistent Context Manager mounted successfully")

    # クリーンアップ時に保存
    async def cleanup():
        logger.info("Saving context before cleanup")
        await context.save()

    return cleanup
```

## 使用例

### Simple Context Manager

```python
config = {
    "session": {
        "orchestrator": "loop-basic",
        "context": {
            "module": "context-simple",
            "config": {
                "max_messages": 150,
                "max_tokens": 10000,
                "compact_to_messages": 75
            }
        }
    },
    "providers": [...],
    "tools": [...]
}

session = AmplifierSession(config)
await session.initialize()
```

### Persistent Context Manager

```python
config = {
    "session": {
        "orchestrator": "loop-basic",
        "context": {
            "module": "context-persistent",
            "config": {
                "storage_path": "./context_storage",
                "max_messages": 200,
                "auto_save": True
            }
        }
    },
    "providers": [...],
    "tools": [...]
}

# セッションIDを指定して以前の会話を復元
session = AmplifierSession(config, session_id="previous-session-uuid")
await session.initialize()
```

## コンパクション戦略

### 戦略1: 古いメッセージを削除

```python
async def compact(self):
    self._messages = self._messages[-N:]
```

### 戦略2: 要約を使用

```python
async def compact(self):
    # LLMを使用して古い会話を要約
    summary = await self._summarize_old_messages(self._messages[:-N])
    self._messages = [summary] + self._messages[-N:]
```

### 戦略3: 重要度ベース

```python
async def compact(self):
    # 重要なメッセージ（エラー、ツール呼び出し結果など）を保持
    important = [m for m in self._messages if self._is_important(m)]
    recent = self._messages[-N:]
    self._messages = important + recent
```

## エントリーポイント設定

**pyproject.toml:**

```toml
[project.entry-points."amplifier.modules"]
context-simple = "amplifier_module_context_simple:mount"
context-persistent = "amplifier_module_context_persistent:mount"
```

## 次のステップ

- [Hook実装例](./hook-example.md)でコンテキストの監視方法を学ぶ
- [Orchestrator実装例](./orchestrator-example.md)でコンテキストの使用方法を確認
