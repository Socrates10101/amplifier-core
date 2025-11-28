"""
Token Counter ユーティリティ

トークン数の計算を行うユーティリティクラスです。
複数の計算方法をサポートし、環境に応じて最適な方法を選択します。

計算方法:
1. tiktoken ライブラリ（推奨、正確）
2. 正規表現ベース（依存なし、概算）
3. 文字数ベース（最も単純、概算）
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# tiktoken が利用可能かチェック
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.debug("tiktoken not available, using fallback token counting")


class TokenCounter:
    """
    トークン数を計算するユーティリティクラス。

    Usage:
        counter = TokenCounter(method="auto")
        count = counter.count("Hello, world!")
        message_count = counter.count_message({"role": "user", "content": "Hello!"})
    """

    # トークン計算方法
    METHOD_TIKTOKEN = "tiktoken"
    METHOD_REGEX = "regex"
    METHOD_CHAR = "char"
    METHOD_AUTO = "auto"

    # Claude モデルは cl100k_base エンコーディングに近い
    DEFAULT_ENCODING = "cl100k_base"

    def __init__(
        self,
        method: str = "auto",
        encoding: str | None = None,
        chars_per_token: int = 4,
    ):
        """
        Args:
            method: 計算方法（"tiktoken", "regex", "char", "auto"）
            encoding: tiktoken エンコーディング名（デフォルト: cl100k_base）
            chars_per_token: 文字数ベース計算時の1トークンあたり文字数
        """
        self._method = method
        self._encoding_name = encoding or self.DEFAULT_ENCODING
        self._chars_per_token = chars_per_token
        self._encoder = None

        # 実際に使用するメソッドを決定
        if method == self.METHOD_AUTO:
            if TIKTOKEN_AVAILABLE:
                self._actual_method = self.METHOD_TIKTOKEN
            else:
                self._actual_method = self.METHOD_REGEX
        else:
            self._actual_method = method

        # tiktoken エンコーダーを初期化
        if self._actual_method == self.METHOD_TIKTOKEN and TIKTOKEN_AVAILABLE:
            try:
                self._encoder = tiktoken.get_encoding(self._encoding_name)
                logger.info(f"Using tiktoken with encoding: {self._encoding_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize tiktoken: {e}, falling back to regex")
                self._actual_method = self.METHOD_REGEX

        logger.info(f"TokenCounter initialized with method: {self._actual_method}")

    @property
    def method(self) -> str:
        """実際に使用している計算方法"""
        return self._actual_method

    def count(self, text: str) -> int:
        """
        テキストのトークン数を計算。

        Args:
            text: 対象テキスト

        Returns:
            トークン数
        """
        if not text:
            return 0

        if self._actual_method == self.METHOD_TIKTOKEN and self._encoder:
            return len(self._encoder.encode(text))
        elif self._actual_method == self.METHOD_REGEX:
            return self._count_regex(text)
        else:
            return self._count_char(text)

    def count_message(self, message: dict[str, Any]) -> int:
        """
        メッセージのトークン数を計算。

        メッセージ構造のオーバーヘッド（role、区切り文字など）も考慮します。

        Args:
            message: メッセージ dict（role, content を含む）

        Returns:
            トークン数
        """
        total = 0

        # メッセージオーバーヘッド（role + 区切り）
        # Claude API では約4トークン程度のオーバーヘッド
        MESSAGE_OVERHEAD = 4

        # role のトークン数
        role = message.get("role", "")
        total += self.count(role)

        # content のトークン数
        content = message.get("content")
        if content:
            if isinstance(content, str):
                total += self.count(content)
            elif isinstance(content, list):
                # ContentBlock のリストの場合
                for block in content:
                    if isinstance(block, dict):
                        # TextBlock
                        if block.get("type") == "text":
                            total += self.count(block.get("text", ""))
                        # ToolCallBlock
                        elif block.get("type") == "tool_call":
                            total += self.count(block.get("name", ""))
                            input_str = str(block.get("input", {}))
                            total += self.count(input_str)
                        # ThinkingBlock
                        elif block.get("type") == "thinking":
                            total += self.count(block.get("thinking", ""))
                    elif hasattr(block, "text"):
                        # TextBlock オブジェクト
                        total += self.count(block.text)
                    elif hasattr(block, "thinking"):
                        # ThinkingBlock オブジェクト
                        total += self.count(block.thinking)
                    elif hasattr(block, "name"):
                        # ToolCallBlock オブジェクト
                        total += self.count(block.name)
                        total += self.count(str(getattr(block, "input", {})))

        # tool_call_id のトークン数
        tool_call_id = message.get("tool_call_id")
        if tool_call_id:
            total += self.count(tool_call_id)

        # name のトークン数
        name = message.get("name")
        if name:
            total += self.count(name)

        return total + MESSAGE_OVERHEAD

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        """
        メッセージリスト全体のトークン数を計算。

        Args:
            messages: メッセージのリスト

        Returns:
            合計トークン数
        """
        return sum(self.count_message(msg) for msg in messages)

    def _count_regex(self, text: str) -> int:
        """
        正規表現ベースでトークン数を概算。

        単語、句読点、空白を個別のトークンとしてカウント。
        """
        # 単語、句読点、空白をトークンとして分割
        tokens = re.findall(r'\w+|[^\w\s]|\s+', text)
        return len(tokens)

    def _count_char(self, text: str) -> int:
        """
        文字数ベースでトークン数を概算。

        一般的に 4 文字 ≈ 1 トークン。
        """
        return max(1, len(text) // self._chars_per_token)


class TokenBudget:
    """
    トークン予算を管理するクラス。

    コンテキストの使用量を追跡し、警告やコンパクションのタイミングを判定します。

    Usage:
        budget = TokenBudget(max_tokens=8000, warning_threshold=0.8)
        budget.add(100)

        if budget.should_warn():
            print(f"Warning: {budget.usage_percentage:.1%} of budget used")

        if budget.is_exceeded():
            # コンパクションが必要
            ...
    """

    def __init__(
        self,
        max_tokens: int = 8000,
        warning_threshold: float = 0.8,
        compact_threshold: float = 0.75,
    ):
        """
        Args:
            max_tokens: 最大トークン数
            warning_threshold: 警告を発する使用率（0.0 - 1.0）
            compact_threshold: コンパクションを推奨する使用率
        """
        self._max_tokens = max_tokens
        self._warning_threshold = warning_threshold
        self._compact_threshold = compact_threshold
        self._current_tokens = 0

    @property
    def max_tokens(self) -> int:
        """最大トークン数"""
        return self._max_tokens

    @property
    def current_tokens(self) -> int:
        """現在のトークン数"""
        return self._current_tokens

    @property
    def remaining_tokens(self) -> int:
        """残りトークン数"""
        return max(0, self._max_tokens - self._current_tokens)

    @property
    def usage_percentage(self) -> float:
        """使用率（0.0 - 1.0）"""
        if self._max_tokens == 0:
            return 0.0
        return self._current_tokens / self._max_tokens

    def add(self, tokens: int) -> None:
        """トークン数を追加"""
        self._current_tokens += tokens

    def subtract(self, tokens: int) -> None:
        """トークン数を減算"""
        self._current_tokens = max(0, self._current_tokens - tokens)

    def set(self, tokens: int) -> None:
        """トークン数を設定"""
        self._current_tokens = max(0, tokens)

    def reset(self) -> None:
        """トークン数をリセット"""
        self._current_tokens = 0

    def should_warn(self) -> bool:
        """警告を発すべきかどうか"""
        return self.usage_percentage >= self._warning_threshold

    def should_compact(self) -> bool:
        """コンパクションを推奨するかどうか"""
        return self.usage_percentage >= self._compact_threshold

    def is_exceeded(self) -> bool:
        """予算を超過しているかどうか"""
        return self._current_tokens >= self._max_tokens

    def get_status(self) -> dict[str, Any]:
        """現在の状態を辞書として取得"""
        return {
            "current_tokens": self._current_tokens,
            "max_tokens": self._max_tokens,
            "remaining_tokens": self.remaining_tokens,
            "usage_percentage": self.usage_percentage,
            "should_warn": self.should_warn(),
            "should_compact": self.should_compact(),
            "is_exceeded": self.is_exceeded(),
        }
