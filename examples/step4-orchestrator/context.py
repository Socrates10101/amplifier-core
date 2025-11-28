"""
Simple Context Manager 実装

Amplifier Core の ContextManager プロトコルに準拠したコンテキスト管理実装。
会話履歴の保持とコンパクションを担当します。

ContextManager プロトコル:
    - add_message(message) -> None
    - get_messages() -> list[dict]
    - should_compact() -> bool
    - compact() -> None
    - clear() -> None
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SimpleContextManager:
    """
    シンプルなコンテキストマネージャー。

    会話履歴をメモリ内で管理し、必要に応じてコンパクションを行います。

    ContextManager プロトコル実装:
        - add_message: メッセージを履歴に追加
        - get_messages: 全履歴を取得
        - should_compact: コンパクションが必要か判定
        - compact: 履歴を圧縮
        - clear: 履歴をクリア
    """

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - max_messages: 最大メッセージ数（デフォルト: 100）
                - compact_threshold: コンパクション閾値（デフォルト: 80）
                - keep_system: システムメッセージを保持するか（デフォルト: True）
                - keep_recent: コンパクト時に保持する最近のメッセージ数（デフォルト: 20）
        """
        self._max_messages = config.get("max_messages", 100)
        self._compact_threshold = config.get("compact_threshold", 80)
        self._keep_system = config.get("keep_system", True)
        self._keep_recent = config.get("keep_recent", 20)

        self._messages: list[dict[str, Any]] = []
        self._system_messages: list[dict[str, Any]] = []

        logger.info(
            f"SimpleContextManager initialized: "
            f"max_messages={self._max_messages}, "
            f"compact_threshold={self._compact_threshold}"
        )

    async def add_message(self, message: dict[str, Any]) -> None:
        """
        メッセージを履歴に追加。

        Args:
            message: 追加するメッセージ
                - role: "system" | "user" | "assistant" | "tool"
                - content: メッセージ内容
                - その他のメタデータ（tool_call_id など）
        """
        # システムメッセージは別管理
        if message.get("role") == "system":
            self._system_messages.append(message)
            logger.debug(f"Added system message")
        else:
            self._messages.append(message)
            logger.debug(f"Added {message.get('role')} message (total: {len(self._messages)})")

    async def get_messages(self) -> list[dict[str, Any]]:
        """
        全メッセージを取得。

        Returns:
            システムメッセージ + 会話履歴
        """
        if self._keep_system:
            return self._system_messages + self._messages
        return self._messages.copy()

    async def should_compact(self) -> bool:
        """
        コンパクションが必要か判定。

        Returns:
            メッセージ数が閾値を超えたら True
        """
        return len(self._messages) >= self._compact_threshold

    async def compact(self) -> None:
        """
        履歴を圧縮。

        古いメッセージを削除し、最近のメッセージのみ保持。
        システムメッセージは保持される（keep_system=True の場合）。
        """
        if len(self._messages) <= self._keep_recent:
            logger.debug("Not enough messages to compact")
            return

        old_count = len(self._messages)

        # 最近のメッセージのみ保持
        self._messages = self._messages[-self._keep_recent:]

        logger.info(
            f"Context compacted: {old_count} -> {len(self._messages)} messages"
        )

    async def clear(self) -> None:
        """全メッセージをクリア。"""
        self._messages.clear()
        self._system_messages.clear()
        logger.info("Context cleared")

    # 追加のユーティリティメソッド

    @property
    def message_count(self) -> int:
        """現在のメッセージ数"""
        return len(self._messages) + len(self._system_messages)

    async def add_system_prompt(self, content: str) -> None:
        """
        システムプロンプトを追加（便利メソッド）。

        Args:
            content: システムプロンプトの内容
        """
        await self.add_message({
            "role": "system",
            "content": content,
        })

    async def get_last_message(self) -> dict[str, Any] | None:
        """最後のメッセージを取得"""
        if self._messages:
            return self._messages[-1]
        return None

    async def get_messages_by_role(self, role: str) -> list[dict[str, Any]]:
        """指定ロールのメッセージのみ取得"""
        if role == "system":
            return self._system_messages.copy()
        return [m for m in self._messages if m.get("role") == role]
