# Provider実装例

ProviderはLLMバックエンドとの通信を担当するモジュールです。

## Providerプロトコル

**定義:** `interfaces.py:52-95`

```python
@runtime_checkable
class Provider(Protocol):
    @property
    def name(self) -> str:
        """プロバイダー名"""
        ...

    async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
        """
        チャット補完を生成。

        Args:
            request: ChatRequest（REQUEST_ENVELOPE_V1仕様）
            **kwargs: プロバイダー固有のオプション

        Returns:
            ChatResponse
        """
        ...

    def parse_tool_calls(self, response: ChatResponse) -> list[ToolCall]:
        """
        レスポンスからツール呼び出しを抽出。

        Args:
            response: ChatResponse

        Returns:
            ツール呼び出しのリスト
        """
        ...
```

## 完全な実装例: Anthropic Provider

```python
"""
Anthropic Provider モジュール

Anthropic APIを使用してチャット補完を生成します。
"""

import logging
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import ContentBlock, MessageStreamEvent
from amplifier_core import ChatRequest, ChatResponse, ToolCall
from amplifier_core import TextBlock, ThinkingBlock, ToolCallBlock, Usage
from amplifier_core.coordinator import ModuleCoordinator

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Anthropic APIプロバイダー"""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: 設定
                - api_key: Anthropic APIキー
                - default_model: デフォルトモデル（デフォルト: claude-sonnet-4-5-20250929）
                - default_max_tokens: デフォルト最大トークン数（デフォルト: 4096）
        """
        self.name = "anthropic"
        self._api_key = config.get("api_key")
        if not self._api_key:
            raise ValueError("Anthropic API key is required")

        self._default_model = config.get("default_model", "claude-sonnet-4-5-20250929")
        self._default_max_tokens = config.get("default_max_tokens", 4096)

        self._client = AsyncAnthropic(api_key=self._api_key)

        # 統計
        self.request_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def complete(
        self,
        request: ChatRequest,
        **kwargs
    ) -> ChatResponse:
        """
        チャット補完を生成。

        Args:
            request: ChatRequest
            **kwargs: Anthropic固有のオプション
                - stream: ストリーミング有効化（デフォルト: False）

        Returns:
            ChatResponse
        """
        self.request_count += 1

        # ChatRequestからAnthropic APIパラメータに変換
        messages = self._convert_messages(request.messages)
        tools = self._convert_tools(request.tools) if request.tools else None

        model = kwargs.get("model", self._default_model)
        max_tokens = request.max_output_tokens or self._default_max_tokens
        temperature = request.temperature or 1.0

        logger.info(f"Requesting completion from {model}")

        try:
            # APIリクエスト
            response = await self._client.messages.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
                stream=kwargs.get("stream", False)
            )

            # ChatResponseに変換
            chat_response = self._convert_response(response)

            # 統計更新
            if chat_response.usage:
                self.total_input_tokens += chat_response.usage.input_tokens
                self.total_output_tokens += chat_response.usage.output_tokens

            logger.info(f"Completion received: {chat_response.usage}")

            return chat_response

        except Exception as e:
            logger.error(f"API request failed: {e}")
            raise

    def parse_tool_calls(self, response: ChatResponse) -> list[ToolCall]:
        """
        レスポンスからツール呼び出しを抽出。

        Args:
            response: ChatResponse

        Returns:
            ToolCallのリスト
        """
        tool_calls = []

        for block in response.content:
            if isinstance(block, ToolCallBlock):
                tool_calls.append(
                    ToolCall(
                        tool=block.name,
                        arguments=block.input,
                        id=block.id
                    )
                )

        return tool_calls

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """ChatRequestのメッセージをAnthropic形式に変換"""
        converted = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # system メッセージは別扱い（Anthropic APIではsystemパラメータ）
            if role == "system":
                continue

            # tool メッセージの変換
            if role == "tool":
                converted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id"),
                            "content": content
                        }
                    ]
                })
            else:
                converted.append({
                    "role": role,
                    "content": content
                })

        return converted

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """ツール仕様をAnthropic形式に変換"""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool.get("parameters", {})
            }
            for tool in tools
        ]

    def _convert_response(self, response: Any) -> ChatResponse:
        """Anthropic APIレスポンスをChatResponseに変換"""
        content_blocks = []

        for block in response.content:
            if block.type == "text":
                content_blocks.append(TextBlock(text=block.text))

            elif block.type == "thinking":
                # Anthropic拡張思考ブロック
                content_blocks.append(ThinkingBlock(
                    thinking=block.thinking,
                    signature=block.signature
                ))

            elif block.type == "tool_use":
                content_blocks.append(ToolCallBlock(
                    id=block.id,
                    name=block.name,
                    input=block.input
                ))

        # Usage情報
        usage = Usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens
        )

        return ChatResponse(
            content=content_blocks,
            usage=usage
        )


async def mount(coordinator: ModuleCoordinator, config: dict):
    """
    Anthropic Providerをマウント。

    Args:
        coordinator: ModuleCoordinator
        config: 設定
            - api_key: Anthropic APIキー（必須）
            - default_model: デフォルトモデル
            - default_max_tokens: デフォルト最大トークン数

    Returns:
        cleanup関数
    """
    logger.info("Mounting Anthropic provider")

    # Providerインスタンス作成
    provider = AnthropicProvider(config)

    # Coordinatorにマウント
    await coordinator.mount("providers", provider, name="anthropic")

    # メトリクスをコントリビューション
    coordinator.register_contributor(
        "metrics.providers",
        "provider-anthropic",
        lambda: {
            "name": "anthropic",
            "requests": provider.request_count,
            "input_tokens": provider.total_input_tokens,
            "output_tokens": provider.total_output_tokens,
        }
    )

    logger.info("Anthropic provider mounted successfully")

    # クリーンアップ関数
    async def cleanup():
        logger.info("Cleaning up Anthropic provider")
        await provider._client.close()

    return cleanup
```

## 使用例

### 設定

```python
config = {
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple"
    },
    "providers": [
        {
            "module": "provider-anthropic",
            "config": {
                "api_key": "sk-ant-...",
                "default_model": "claude-sonnet-4-5-20250929",
                "default_max_tokens": 4096
            }
        }
    ],
    "tools": [],
    "hooks": []
}

session = AmplifierSession(config)
await session.initialize()
```

### 実行

```python
result = await session.execute("Hello, Claude!")
print(result)
```

## ストリーミング対応版

ストリーミング時はイベントを発行します：

```python
async def complete(self, request: ChatRequest, **kwargs) -> ChatResponse:
    if kwargs.get("stream", False):
        # ストリーミングモード
        content_blocks = []
        current_text = ""

        async with self._client.messages.stream(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    await self._emit_event("content_block:start", {
                        "index": event.index,
                        "type": event.content_block.type
                    })

                elif event.type == "content_block_delta":
                    delta = event.delta.text if hasattr(event.delta, "text") else ""
                    current_text += delta

                    await self._emit_event("content_block:delta", {
                        "index": event.index,
                        "delta": delta
                    })

                elif event.type == "content_block_stop":
                    await self._emit_event("content_block:end", {
                        "index": event.index
                    })

                    content_blocks.append(TextBlock(text=current_text))
                    current_text = ""

        # 最終レスポンスを返す
        return ChatResponse(content=content_blocks, usage=...)
    else:
        # 通常モード
        ...
```

## エントリーポイント設定

**pyproject.toml:**

```toml
[project]
name = "amplifier-module-provider-anthropic"
version = "1.0.0"
dependencies = [
    "amplifier-core>=1.0.0",
    "anthropic>=0.18.0"
]

[project.entry-points."amplifier.modules"]
provider-anthropic = "amplifier_module_provider_anthropic:mount"
```

## 次のステップ

- [Tool実装例](./tool-example.md)でツールモジュールを理解
- [Orchestrator実装例](./orchestrator-example.md)でProviderの呼び出し方を確認
