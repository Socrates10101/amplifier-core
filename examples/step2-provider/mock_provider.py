"""
Step 2: モックプロバイダー実装

このモジュールでは、Providerプロトコルを実装する様々なモックプロバイダーを定義します。
各プロバイダーは異なる振る舞いを示し、プロバイダーの仕組みを理解するのに役立ちます。
"""

from amplifier_core.message_models import (
    ChatRequest,
    ChatResponse,
    Message,
    TextBlock,
    ThinkingBlock,
    ToolCallBlock,
    ToolCall,
    Usage,
)


class EchoProvider:
    """
    最もシンプルなプロバイダー - ユーザー入力をエコーバック

    このプロバイダーは:
    - ユーザーの最後のメッセージを取得
    - そのままエコーバックする
    - ツールコールは生成しない

    Providerプロトコルの最小実装を示します。
    """

    @property
    def name(self) -> str:
        return "echo"

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """ユーザーメッセージをエコーバック"""
        user_message = self._extract_last_user_message(request)

        return ChatResponse(
            content=[TextBlock(type="text", text=f"[Echo] {user_message}")],
            tool_calls=None,
            usage=Usage(
                input_tokens=len(user_message.split()),
                output_tokens=len(user_message.split()) + 1,
                total_tokens=len(user_message.split()) * 2 + 1,
            ),
            finish_reason="stop",
        )

    def parse_tool_calls(self, response: ChatResponse) -> list[ToolCall]:
        """ツールコールを解析（このプロバイダーは常に空）"""
        return response.tool_calls or []

    def _extract_last_user_message(self, request: ChatRequest) -> str:
        """リクエストから最後のユーザーメッセージを抽出"""
        for msg in reversed(request.messages):
            if msg.role == "user":
                if isinstance(msg.content, str):
                    return msg.content
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        return block.text
        return ""


class ThinkingProvider:
    """
    思考プロセスを含むプロバイダー

    このプロバイダーは:
    - ThinkingBlockを使って「思考過程」を表現
    - その後にテキスト応答を返す
    - Anthropicの拡張思考機能をシミュレート
    """

    @property
    def name(self) -> str:
        return "thinking"

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """思考ブロックとテキスト応答を返す"""
        user_message = self._extract_last_user_message(request)

        # 思考プロセスを生成
        thinking_text = f"ユーザーは「{user_message}」と言っています。適切な応答を考えます..."

        # 応答を生成
        response_text = f"[Thinking Provider] あなたのメッセージ「{user_message}」を理解しました。"

        return ChatResponse(
            content=[
                ThinkingBlock(
                    type="thinking",
                    thinking=thinking_text,
                    signature="mock-signature-123",
                ),
                TextBlock(type="text", text=response_text),
            ],
            tool_calls=None,
            usage=Usage(
                input_tokens=10,
                output_tokens=25,
                total_tokens=35,
            ),
            finish_reason="stop",
        )

    def parse_tool_calls(self, response: ChatResponse) -> list[ToolCall]:
        return response.tool_calls or []

    def _extract_last_user_message(self, request: ChatRequest) -> str:
        for msg in reversed(request.messages):
            if msg.role == "user":
                if isinstance(msg.content, str):
                    return msg.content
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        return block.text
        return ""


class ToolCallingProvider:
    """
    ツールコールを生成するプロバイダー

    このプロバイダーは:
    - 特定のキーワードを検出するとツールコールを生成
    - "calculate" → calculator ツール
    - "search" → search ツール
    - それ以外はテキスト応答
    """

    @property
    def name(self) -> str:
        return "tool-caller"

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """メッセージを解析してツールコールまたはテキストを返す"""
        user_message = self._extract_last_user_message(request)
        user_lower = user_message.lower()

        # "calculate" キーワードを検出
        if "calculate" in user_lower or "計算" in user_message:
            return self._create_tool_call_response(
                tool_name="calculator",
                tool_input={"expression": "1 + 1"},
                call_id="call_calc_001",
            )

        # "search" キーワードを検出
        if "search" in user_lower or "検索" in user_message:
            return self._create_tool_call_response(
                tool_name="web_search",
                tool_input={"query": user_message},
                call_id="call_search_001",
            )

        # 通常のテキスト応答
        return ChatResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"[Tool Caller] ツールは不要です。メッセージ: {user_message}",
                )
            ],
            tool_calls=None,
            usage=Usage(input_tokens=10, output_tokens=15, total_tokens=25),
            finish_reason="stop",
        )

    def _create_tool_call_response(
        self, tool_name: str, tool_input: dict, call_id: str
    ) -> ChatResponse:
        """ツールコールレスポンスを作成"""
        return ChatResponse(
            content=[
                ToolCallBlock(
                    type="tool_call",
                    id=call_id,
                    name=tool_name,
                    input=tool_input,
                )
            ],
            tool_calls=[
                ToolCall(
                    id=call_id,
                    name=tool_name,
                    arguments=tool_input,
                )
            ],
            usage=Usage(input_tokens=10, output_tokens=20, total_tokens=30),
            finish_reason="tool_use",
        )

    def parse_tool_calls(self, response: ChatResponse) -> list[ToolCall]:
        """レスポンスからツールコールを解析"""
        return response.tool_calls or []

    def _extract_last_user_message(self, request: ChatRequest) -> str:
        for msg in reversed(request.messages):
            if msg.role == "user":
                if isinstance(msg.content, str):
                    return msg.content
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        return block.text
        return ""


class ConversationalProvider:
    """
    会話履歴を考慮するプロバイダー

    このプロバイダーは:
    - 会話の長さに応じて応答を変える
    - システムメッセージを認識する
    - 会話コンテキストをレスポンスに反映
    """

    @property
    def name(self) -> str:
        return "conversational"

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """会話履歴を考慮した応答を生成"""
        # 会話の統計を収集
        stats = self._analyze_conversation(request)

        # 応答を構築
        response_parts = [
            f"[Conversational Provider]",
            f"  会話ターン数: {stats['turn_count']}",
            f"  システムメッセージ: {'あり' if stats['has_system'] else 'なし'}",
            f"  最後のユーザー入力: {stats['last_user_message'][:50]}...",
        ]

        return ChatResponse(
            content=[TextBlock(type="text", text="\n".join(response_parts))],
            tool_calls=None,
            usage=Usage(
                input_tokens=stats["total_tokens"],
                output_tokens=20,
                total_tokens=stats["total_tokens"] + 20,
            ),
            finish_reason="stop",
        )

    def parse_tool_calls(self, response: ChatResponse) -> list[ToolCall]:
        return response.tool_calls or []

    def _analyze_conversation(self, request: ChatRequest) -> dict:
        """会話を分析して統計を返す"""
        stats = {
            "turn_count": 0,
            "has_system": False,
            "last_user_message": "",
            "total_tokens": 0,
        }

        for msg in request.messages:
            if msg.role == "system":
                stats["has_system"] = True
            elif msg.role in ("user", "assistant"):
                stats["turn_count"] += 1

            # トークン数を推定（簡易）
            content_text = self._get_message_text(msg)
            stats["total_tokens"] += len(content_text.split())

            if msg.role == "user":
                stats["last_user_message"] = content_text

        return stats

    def _get_message_text(self, msg: Message) -> str:
        """メッセージからテキストを抽出"""
        if isinstance(msg.content, str):
            return msg.content
        texts = []
        for block in msg.content:
            if isinstance(block, TextBlock):
                texts.append(block.text)
        return " ".join(texts)
