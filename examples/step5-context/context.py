"""
Advanced Context Manager 実装

Amplifier Core の ContextManager プロトコルに準拠した高度なコンテキスト管理実装。
トークン計算と要約コンパクションをサポートします。

ContextManager プロトコル:
    - add_message(message) -> None
    - get_messages() -> list[dict]
    - should_compact() -> bool
    - compact() -> None
    - clear() -> None

拡張機能:
    - トークン数による制限管理
    - LLM を使用した要約コンパクション
    - 重要度ベースのメッセージ保持
"""

import logging
from typing import Any, Callable, Awaitable

from tokenizer import TokenCounter, TokenBudget

logger = logging.getLogger(__name__)


class AdvancedContextManager:
    """
    高度なコンテキストマネージャー。

    Step 4 の SimpleContextManager を拡張し、以下の機能を追加:
    1. トークン数による制限管理
    2. LLM を使用した要約コンパクション
    3. 重要度ベースのメッセージ保持

    ContextManager プロトコル実装:
        - add_message: メッセージを履歴に追加（トークン数も追跡）
        - get_messages: 全履歴を取得
        - should_compact: コンパクションが必要か判定（トークン数ベース）
        - compact: 要約コンパクションを実行
        - clear: 履歴をクリア
    """

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - max_tokens: 最大トークン数（デフォルト: 8000）
                - compact_threshold: コンパクション閾値トークン数（デフォルト: 6000）
                - keep_recent: 常に保持する最新メッセージ数（デフォルト: 10）
                - keep_system: システムメッセージを保持するか（デフォルト: True）
                - use_summary: 要約コンパクションを使用するか（デフォルト: True）
                - summary_max_tokens: 要約の最大トークン数（デフォルト: 500）
                - token_method: トークン計算方法（デフォルト: "auto"）
        """
        self._max_tokens = config.get("max_tokens", 8000)
        self._compact_threshold = config.get("compact_threshold", 6000)
        self._keep_recent = config.get("keep_recent", 10)
        self._keep_system = config.get("keep_system", True)
        self._use_summary = config.get("use_summary", True)
        self._summary_max_tokens = config.get("summary_max_tokens", 500)

        # トークンカウンターと予算管理
        self._token_counter = TokenCounter(method=config.get("token_method", "auto"))
        self._token_budget = TokenBudget(
            max_tokens=self._max_tokens,
            compact_threshold=self._compact_threshold / self._max_tokens,
        )

        # メッセージストレージ
        self._messages: list[dict[str, Any]] = []
        self._system_messages: list[dict[str, Any]] = []

        # 要約プロバイダー（外部から設定）
        self._summary_provider: Any = None
        self._summary_callback: Callable[[str], Awaitable[str]] | None = None

        # 統計情報
        self._compact_count = 0
        self._total_messages_added = 0

        logger.info(
            f"AdvancedContextManager initialized: "
            f"max_tokens={self._max_tokens}, "
            f"compact_threshold={self._compact_threshold}, "
            f"use_summary={self._use_summary}"
        )

    # ============================================
    # ContextManager プロトコル実装
    # ============================================

    async def add_message(self, message: dict[str, Any]) -> None:
        """
        メッセージを履歴に追加。

        Args:
            message: 追加するメッセージ
                - role: "system" | "user" | "assistant" | "tool"
                - content: メッセージ内容
                - その他のメタデータ（tool_call_id など）
        """
        # トークン数を計算
        tokens = self._token_counter.count_message(message)

        # メッセージにトークン数を記録（デバッグ用）
        message_with_tokens = {**message, "_tokens": tokens}

        # システムメッセージは別管理
        if message.get("role") == "system":
            self._system_messages.append(message_with_tokens)
            logger.debug(f"Added system message ({tokens} tokens)")
        else:
            self._messages.append(message_with_tokens)
            logger.debug(
                f"Added {message.get('role')} message "
                f"({tokens} tokens, total: {len(self._messages)} messages)"
            )

        # トークン予算を更新
        self._token_budget.add(tokens)
        self._total_messages_added += 1

        # 警告チェック
        if self._token_budget.should_warn():
            logger.warning(
                f"Token budget warning: "
                f"{self._token_budget.current_tokens}/{self._max_tokens} "
                f"({self._token_budget.usage_percentage:.1%})"
            )

    async def get_messages(self) -> list[dict[str, Any]]:
        """
        全メッセージを取得。

        Returns:
            システムメッセージ + 会話履歴（_tokens フィールドは除外）
        """
        # _tokens フィールドを除外してコピー
        def clean_message(msg: dict[str, Any]) -> dict[str, Any]:
            return {k: v for k, v in msg.items() if not k.startswith("_")}

        messages = []

        if self._keep_system:
            messages.extend(clean_message(m) for m in self._system_messages)

        messages.extend(clean_message(m) for m in self._messages)

        return messages

    async def should_compact(self) -> bool:
        """
        コンパクションが必要か判定。

        Returns:
            トークン数が閾値を超えたら True
        """
        return self._token_budget.should_compact()

    async def compact(self) -> None:
        """
        コンテキストを圧縮。

        戦略:
        1. システムメッセージを保持
        2. 重要なメッセージを抽出
        3. 古い会話を要約（use_summary=True の場合）
        4. 最新のメッセージを保持
        """
        if len(self._messages) <= self._keep_recent:
            logger.debug("Not enough messages to compact")
            return

        old_count = len(self._messages)
        old_tokens = self._token_budget.current_tokens

        logger.info(
            f"Starting compaction: "
            f"{old_count} messages, {old_tokens} tokens"
        )

        # 1. 重要なメッセージを抽出
        important_messages = [
            msg for msg in self._messages[:-self._keep_recent]
            if self._is_important(msg)
        ]

        # 2. 最新のメッセージを取得
        recent_messages = self._messages[-self._keep_recent:]

        # 3. 要約を生成（use_summary=True かつプロバイダーが設定されている場合）
        summary_message = None
        if self._use_summary and self._summary_callback:
            # 要約対象のメッセージ（重要なもの以外）
            messages_to_summarize = [
                msg for msg in self._messages[:-self._keep_recent]
                if not self._is_important(msg)
            ]

            if messages_to_summarize:
                try:
                    summary_text = await self._generate_summary(messages_to_summarize)
                    summary_message = {
                        "role": "system",
                        "content": f"[Previous conversation summary]\n{summary_text}",
                        "metadata": {
                            "type": "summary",
                            "original_count": len(messages_to_summarize),
                        },
                    }
                    logger.info(f"Generated summary for {len(messages_to_summarize)} messages")
                except Exception as e:
                    logger.error(f"Failed to generate summary: {e}")
                    # 要約失敗時は単純削除にフォールバック
                    summary_message = {
                        "role": "system",
                        "content": f"[Previous conversation: {len(messages_to_summarize)} messages omitted]",
                        "metadata": {"type": "truncation"},
                    }
        else:
            # 要約なしの場合は単純に削除メッセージを追加
            omitted_count = len(self._messages) - self._keep_recent - len(important_messages)
            if omitted_count > 0:
                summary_message = {
                    "role": "system",
                    "content": f"[Previous conversation: {omitted_count} messages omitted]",
                    "metadata": {"type": "truncation"},
                }

        # 4. 新しいメッセージリストを構築
        new_messages = []

        if summary_message:
            new_messages.append(summary_message)

        new_messages.extend(important_messages)
        new_messages.extend(recent_messages)

        self._messages = new_messages

        # 5. トークン数を再計算
        self._recalculate_tokens()

        self._compact_count += 1

        logger.info(
            f"Compaction complete: "
            f"{old_count} -> {len(self._messages)} messages, "
            f"{old_tokens} -> {self._token_budget.current_tokens} tokens"
        )

    async def clear(self) -> None:
        """全メッセージをクリア。"""
        self._messages.clear()
        self._system_messages.clear()
        self._token_budget.reset()
        logger.info("Context cleared")

    # ============================================
    # 追加のユーティリティメソッド
    # ============================================

    @property
    def total_tokens(self) -> int:
        """現在の合計トークン数"""
        return self._token_budget.current_tokens

    @property
    def message_count(self) -> int:
        """現在のメッセージ数"""
        return len(self._messages) + len(self._system_messages)

    @property
    def compact_count(self) -> int:
        """コンパクション実行回数"""
        return self._compact_count

    @property
    def token_budget(self) -> TokenBudget:
        """トークン予算オブジェクト"""
        return self._token_budget

    def set_summary_callback(
        self,
        callback: Callable[[str], Awaitable[str]]
    ) -> None:
        """
        要約生成コールバックを設定。

        Args:
            callback: テキストを受け取って要約を返す非同期関数
        """
        self._summary_callback = callback
        logger.info("Summary callback set")

    def set_summary_provider(self, provider: Any) -> None:
        """
        要約に使用するプロバイダーを設定。

        Args:
            provider: Provider プロトコルを実装したオブジェクト
        """
        self._summary_provider = provider
        logger.info(f"Summary provider set: {getattr(provider, 'name', 'unknown')}")

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
            msg = self._messages[-1]
            return {k: v for k, v in msg.items() if not k.startswith("_")}
        return None

    async def get_messages_by_role(self, role: str) -> list[dict[str, Any]]:
        """指定ロールのメッセージのみ取得"""
        if role == "system":
            return [
                {k: v for k, v in m.items() if not k.startswith("_")}
                for m in self._system_messages
            ]
        return [
            {k: v for k, v in m.items() if not k.startswith("_")}
            for m in self._messages
            if m.get("role") == role
        ]

    def get_stats(self) -> dict[str, Any]:
        """統計情報を取得"""
        return {
            "message_count": self.message_count,
            "system_message_count": len(self._system_messages),
            "conversation_message_count": len(self._messages),
            "total_tokens": self.total_tokens,
            "max_tokens": self._max_tokens,
            "usage_percentage": self._token_budget.usage_percentage,
            "compact_count": self._compact_count,
            "total_messages_added": self._total_messages_added,
            "token_method": self._token_counter.method,
        }

    # ============================================
    # プライベートメソッド
    # ============================================

    def _is_important(self, message: dict[str, Any]) -> bool:
        """
        メッセージの重要度を判定。

        重要と判定されるメッセージ:
        - ツール結果（role="tool"）
        - エラーを含むメッセージ
        - メタデータで important=True とマークされたメッセージ
        """
        role = message.get("role")

        # ツール結果は重要
        if role == "tool":
            return True

        # エラーを含むメッセージは重要
        content = message.get("content", "")
        if isinstance(content, str):
            if "error" in content.lower() or "[Error:" in content:
                return True

        # メタデータで重要とマークされたメッセージ
        metadata = message.get("metadata", {})
        if isinstance(metadata, dict) and metadata.get("important"):
            return True

        return False

    def _recalculate_tokens(self) -> None:
        """トークン数を再計算"""
        # システムメッセージのトークン数
        system_tokens = sum(
            msg.get("_tokens", self._token_counter.count_message(msg))
            for msg in self._system_messages
        )

        # 会話メッセージのトークン数
        message_tokens = sum(
            msg.get("_tokens", self._token_counter.count_message(msg))
            for msg in self._messages
        )

        self._token_budget.set(system_tokens + message_tokens)

    async def _generate_summary(self, messages: list[dict[str, Any]]) -> str:
        """
        メッセージを要約。

        Args:
            messages: 要約対象のメッセージ

        Returns:
            要約テキスト
        """
        # コールバックが設定されている場合はそれを使用
        if self._summary_callback:
            # メッセージを会話形式のテキストに変換
            conversation_text = self._format_conversation(messages)
            return await self._summary_callback(conversation_text)

        # プロバイダーが設定されている場合
        if self._summary_provider:
            from amplifier_core.message_models import ChatRequest, Message, TextBlock

            conversation_text = self._format_conversation(messages)

            request = ChatRequest(
                messages=[
                    Message(
                        role="user",
                        content=[TextBlock(
                            type="text",
                            text=(
                                "Please summarize the following conversation briefly. "
                                "Focus on key decisions, important facts, and the overall context. "
                                f"Keep the summary under {self._summary_max_tokens} tokens.\n\n"
                                f"Conversation:\n{conversation_text}"
                            ),
                        )],
                    )
                ],
                max_output_tokens=self._summary_max_tokens,
            )

            response = await self._summary_provider.complete(request)

            # レスポンスからテキストを抽出
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")

            return "[Summary generation failed]"

        # どちらも設定されていない場合はプレースホルダー
        return f"[Summarized {len(messages)} previous messages]"

    def _format_conversation(self, messages: list[dict[str, Any]]) -> str:
        """
        メッセージを会話形式のテキストに変換。

        Args:
            messages: メッセージリスト

        Returns:
            会話形式のテキスト
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                # ContentBlock のリストの場合はテキストのみ抽出
                texts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif hasattr(block, "text"):
                        texts.append(block.text)
                text = " ".join(texts)
            else:
                text = str(content)

            lines.append(f"{role}: {text[:500]}{'...' if len(text) > 500 else ''}")

        return "\n".join(lines)


async def mount(coordinator, config: dict):
    """AdvancedContextManager をマウント"""
    logger.info("Mounting AdvancedContextManager")

    context = AdvancedContextManager(config)

    await coordinator.mount("context", context)

    logger.info("AdvancedContextManager mounted successfully")

    return None
