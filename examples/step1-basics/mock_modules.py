"""
Step 1: モックモジュール

最小限のモックモジュールを定義します。
このステップでは、各プロトコルの基本形を理解することが目標です。
"""

from typing import Any

from amplifier_core.message_models import (
    ChatRequest,
    ChatResponse,
    TextBlock,
)
from amplifier_core.models import HookResult, ToolResult


class MockProvider:
    """
    最小限のProviderモック

    Providerプロトコルが要求するもの:
    - name プロパティ
    - complete(request) メソッド
    - parse_tool_calls(response) メソッド
    """

    @property
    def name(self) -> str:
        return "mock-provider"

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """固定レスポンスを返すモック実装"""
        # 最後のユーザーメッセージを取得
        user_message = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                for block in msg.content:
                    if hasattr(block, "text"):
                        user_message = block.text
                        break
                break

        response_text = f"[MockProvider] Received: {user_message}"
        return ChatResponse(
            content=[TextBlock(type="text", text=response_text)],
            tool_calls=None,
            usage=None,
            finish_reason="stop",
        )

    def parse_tool_calls(self, response: ChatResponse) -> list:
        """ツールコールを解析（このモックでは常に空）"""
        return []


class MockContextManager:
    """
    最小限のContextManagerモック

    ContextManagerプロトコルが要求するもの:
    - add_message(message) メソッド
    - get_messages() メソッド
    - should_compact() メソッド
    - compact() メソッド
    - clear() メソッド
    """

    def __init__(self):
        self._messages: list[dict[str, Any]] = []

    async def add_message(self, message: dict[str, Any]) -> None:
        """メッセージを追加"""
        self._messages.append(message)
        print(f"  [Context] Added message: role={message.get('role')}")

    async def get_messages(self) -> list[dict[str, Any]]:
        """全メッセージを取得"""
        return self._messages.copy()

    async def should_compact(self) -> bool:
        """コンパクションが必要かチェック（常にFalse）"""
        return False

    async def compact(self) -> None:
        """コンパクション実行（何もしない）"""
        pass

    async def clear(self) -> None:
        """全メッセージをクリア"""
        self._messages.clear()


class MockOrchestrator:
    """
    最小限のOrchestratorモック

    Orchestratorプロトコルが要求するもの:
    - execute(prompt, context, providers, tools, hooks, coordinator) メソッド
    """

    async def execute(
        self,
        prompt: str,
        context,
        providers: dict,
        tools: dict,
        hooks,
        coordinator=None,
    ) -> str:
        """
        プロンプトを実行して結果を返す

        実際のOrchestratorはここで:
        1. コンテキストからメッセージを取得
        2. プロバイダーにリクエストを送信
        3. ツールコールがあれば実行
        4. ループを繰り返す
        """
        print(f"  [Orchestrator] Executing prompt: {prompt}")

        # 1. イベントを発行（hooks経由）
        if hooks:
            await hooks.emit("prompt:submit", {"prompt": prompt})

        # 2. プロバイダーを使用（最初のプロバイダーを使用）
        provider = list(providers.values())[0] if providers else None
        if provider:
            from amplifier_core.message_models import Message, TextBlock as TB

            request = ChatRequest(
                messages=[
                    Message(
                        role="user",
                        content=[TB(type="text", text=prompt)],
                    )
                ]
            )
            response = await provider.complete(request)

            # レスポンスからテキストを抽出
            result_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    result_text = block.text
                    break
        else:
            result_text = f"[No provider] Echo: {prompt}"

        # 3. 完了イベントを発行
        if hooks:
            await hooks.emit("prompt:complete", {"response": result_text})

        return result_text


class MockTool:
    """
    最小限のToolモック

    Toolプロトコルが要求するもの:
    - name プロパティ
    - description プロパティ
    - execute(input) メソッド
    """

    @property
    def name(self) -> str:
        return "mock-tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        """ツールを実行"""
        print(f"  [Tool] Executing with input: {input}")
        return ToolResult(
            success=True,
            output=f"Tool executed with: {input}",
        )
