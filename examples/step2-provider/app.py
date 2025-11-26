"""
Step 2: Providerの実装

このスクリプトでは、LLMプロバイダーの仕組みを学びます：
1. ChatRequest の構築方法
2. Providerの呼び出し方
3. ChatResponse の解析方法
4. 複数プロバイダーの管理
"""

import asyncio

from amplifier_core import AmplifierSession
from amplifier_core.message_models import (
    ChatRequest,
    Message,
    TextBlock,
    ThinkingBlock,
    ToolCallBlock,
)

from mock_provider import (
    EchoProvider,
    ThinkingProvider,
    ToolCallingProvider,
    ConversationalProvider,
)


async def main():
    print("=" * 60)
    print("Step 2: Providerの実装")
    print("=" * 60)

    # =========================================
    # Part 1: ChatRequestの構築
    # =========================================
    print("\n[Part 1] ChatRequestの構築")
    print("-" * 40)

    # シンプルなリクエスト
    simple_request = ChatRequest(
        messages=[
            Message(
                role="user",
                content=[TextBlock(type="text", text="Hello, Provider!")],
            )
        ]
    )
    print(f"Simple request:")
    print(f"  Messages: {len(simple_request.messages)}")
    print(f"  Role: {simple_request.messages[0].role}")

    # システムメッセージを含むリクエスト
    request_with_system = ChatRequest(
        messages=[
            Message(
                role="system",
                content="You are a helpful assistant.",
            ),
            Message(
                role="user",
                content=[TextBlock(type="text", text="What can you do?")],
            ),
        ]
    )
    print(f"\nRequest with system message:")
    print(f"  Messages: {len(request_with_system.messages)}")
    print(f"  Roles: {[m.role for m in request_with_system.messages]}")

    # =========================================
    # Part 2: 基本的なプロバイダーの使用
    # =========================================
    print("\n[Part 2] 基本的なプロバイダーの使用")
    print("-" * 40)

    echo_provider = EchoProvider()
    print(f"Provider name: {echo_provider.name}")

    # リクエストを送信
    response = await echo_provider.complete(simple_request)
    print(f"\nResponse from EchoProvider:")
    print(f"  Finish reason: {response.finish_reason}")
    print(f"  Content blocks: {len(response.content)}")

    # コンテンツを表示
    for i, block in enumerate(response.content):
        if isinstance(block, TextBlock):
            print(f"  [{i}] TextBlock: {block.text}")

    # 使用量を表示
    if response.usage:
        print(f"  Usage: {response.usage.input_tokens} in / {response.usage.output_tokens} out")

    # =========================================
    # Part 3: 思考プロセスを含むプロバイダー
    # =========================================
    print("\n[Part 3] 思考プロセスを含むプロバイダー")
    print("-" * 40)

    thinking_provider = ThinkingProvider()
    response = await thinking_provider.complete(simple_request)

    print(f"Response from ThinkingProvider:")
    for i, block in enumerate(response.content):
        if isinstance(block, ThinkingBlock):
            print(f"  [{i}] ThinkingBlock: {block.thinking[:50]}...")
        elif isinstance(block, TextBlock):
            print(f"  [{i}] TextBlock: {block.text}")

    # =========================================
    # Part 4: ツールコールを生成するプロバイダー
    # =========================================
    print("\n[Part 4] ツールコールを生成するプロバイダー")
    print("-" * 40)

    tool_provider = ToolCallingProvider()

    # 通常のリクエスト
    normal_request = ChatRequest(
        messages=[
            Message(
                role="user",
                content=[TextBlock(type="text", text="Hello!")],
            )
        ]
    )
    response = await tool_provider.complete(normal_request)
    print(f"Normal request - finish_reason: {response.finish_reason}")
    tool_calls = tool_provider.parse_tool_calls(response)
    print(f"  Tool calls: {len(tool_calls)}")

    # ツールコールをトリガーするリクエスト
    calculate_request = ChatRequest(
        messages=[
            Message(
                role="user",
                content=[TextBlock(type="text", text="Please calculate 1 + 1")],
            )
        ]
    )
    response = await tool_provider.complete(calculate_request)
    print(f"\nCalculate request - finish_reason: {response.finish_reason}")

    # ツールコールを解析
    tool_calls = tool_provider.parse_tool_calls(response)
    print(f"  Tool calls: {len(tool_calls)}")
    for tc in tool_calls:
        print(f"    - {tc.name}(id={tc.id})")
        print(f"      arguments: {tc.arguments}")

    # コンテンツブロックでもツールコールを確認
    for block in response.content:
        if isinstance(block, ToolCallBlock):
            print(f"  ToolCallBlock in content: {block.name}")

    # =========================================
    # Part 5: セッションでの複数プロバイダー管理
    # =========================================
    print("\n[Part 5] セッションでの複数プロバイダー管理")
    print("-" * 40)

    # セッションを作成
    config = {
        "session": {
            "orchestrator": "mock-orchestrator",
            "context": "mock-context",
        }
    }
    session = AmplifierSession(config)

    # 複数のプロバイダーをマウント
    await session.coordinator.mount("providers", EchoProvider(), name="echo")
    await session.coordinator.mount("providers", ThinkingProvider(), name="thinking")
    await session.coordinator.mount("providers", ToolCallingProvider(), name="tool-caller")
    await session.coordinator.mount("providers", ConversationalProvider(), name="conversational")

    # マウントされたプロバイダーを確認
    providers = session.coordinator.get("providers")
    print(f"Mounted providers: {list(providers.keys())}")

    # 各プロバイダーを使用
    test_request = ChatRequest(
        messages=[
            Message(role="user", content=[TextBlock(type="text", text="Test message")])
        ]
    )

    print("\nTesting each provider:")
    for name, provider in providers.items():
        response = await provider.complete(test_request)
        first_text = ""
        for block in response.content:
            if isinstance(block, TextBlock):
                first_text = block.text[:40]
                break
            elif isinstance(block, ThinkingBlock):
                first_text = f"(thinking) {block.thinking[:30]}"
                break
            elif isinstance(block, ToolCallBlock):
                first_text = f"(tool_call) {block.name}"
                break
        print(f"  {name}: {first_text}...")

    # =========================================
    # Part 6: 会話履歴を持つリクエスト
    # =========================================
    print("\n[Part 6] 会話履歴を持つリクエスト")
    print("-" * 40)

    # 複数ターンの会話
    conversation_request = ChatRequest(
        messages=[
            Message(role="system", content="You are a helpful assistant."),
            Message(
                role="user",
                content=[TextBlock(type="text", text="Hello!")],
            ),
            Message(
                role="assistant",
                content=[TextBlock(type="text", text="Hello! How can I help you?")],
            ),
            Message(
                role="user",
                content=[TextBlock(type="text", text="What is 2 + 2?")],
            ),
        ]
    )

    conversational = providers["conversational"]
    response = await conversational.complete(conversation_request)

    print("Response from ConversationalProvider:")
    for block in response.content:
        if isinstance(block, TextBlock):
            for line in block.text.split("\n"):
                print(f"  {line}")

    # =========================================
    # クリーンアップ
    # =========================================
    print("\n[Cleanup]")
    print("-" * 40)
    await session.cleanup()
    print("Session cleaned up")

    print("\n" + "=" * 60)
    print("Step 2 完了!")
    print("=" * 60)
    print("\n次のステップ: Step 3 - Toolの実装")


if __name__ == "__main__":
    asyncio.run(main())
