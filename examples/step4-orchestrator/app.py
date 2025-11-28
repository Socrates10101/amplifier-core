"""
Step 4: Orchestrator の実装

このスクリプトでは、エージェントループを制御する Orchestrator の仕組みを学びます：
1. Orchestrator プロトコルの理解
2. ContextManager プロトコルの理解
3. Provider と Tool の連携
4. 完全なエージェントループの実行

実行方法:
    python app.py              # 基本デモ
    python app.py --with-llm   # Claude CLI 統合デモ（APIキー不要）
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add project root and examples directory to path for module discovery
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from amplifier_core import AmplifierSession
from amplifier_core.loader import ModuleLoader

from orchestrator import BasicLoopOrchestrator
from context import SimpleContextManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def demo_orchestrator_basics():
    """Orchestrator プロトコルの基本デモ"""
    print("\n[Part 1] Orchestrator プロトコルの基本")
    print("-" * 50)

    # Orchestrator の作成
    orchestrator = BasicLoopOrchestrator({
        "max_turns": 5,
        "temperature": 0.7,
    })

    print(f"Orchestrator created:")
    print(f"  max_turns: 5")
    print(f"  temperature: 0.7")

    # Orchestrator の設定
    print(f"\nOrchestrator configuration:")
    print(f"  - max_turns: 最大ターン数")
    print(f"  - provider: 使用するプロバイダー名")
    print(f"  - temperature: LLM の温度パラメータ")
    print(f"  - max_tokens: 最大トークン数")


async def demo_context_manager():
    """ContextManager プロトコルの基本デモ"""
    print("\n[Part 2] ContextManager プロトコルの基本")
    print("-" * 50)

    # ContextManager の作成
    context = SimpleContextManager({
        "max_messages": 100,
        "compact_threshold": 80,
    })

    print(f"ContextManager created:")
    print(f"  max_messages: 100")
    print(f"  compact_threshold: 80")

    # メッセージの追加
    await context.add_message({
        "role": "system",
        "content": "You are a helpful assistant.",
    })
    await context.add_message({
        "role": "user",
        "content": "What is 2 + 2?",
    })
    await context.add_message({
        "role": "assistant",
        "content": "2 + 2 = 4",
    })

    messages = await context.get_messages()
    print(f"\nMessages in context: {len(messages)}")
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if isinstance(content, str):
            content = content[:50] + "..." if len(content) > 50 else content
        print(f"  [{role}]: {content}")

    # コンパクション判定
    should_compact = await context.should_compact()
    print(f"\nShould compact: {should_compact}")


async def demo_full_loop_with_mock():
    """モック Provider を使った完全なエージェントループデモ"""
    print("\n[Part 3] モック Provider での完全なエージェントループ")
    print("-" * 50)

    from amplifier_core.models import ToolCall

    # モック Provider
    class MockProvider:
        name = "mock-provider"
        _call_count = 0

        async def complete(self, request):
            from amplifier_core.message_models import ChatResponse, TextBlock, ToolCallBlock

            self._call_count += 1

            # 最初の呼び出し: ツールを呼び出す
            if self._call_count == 1:
                return ChatResponse(
                    content=[
                        TextBlock(type="text", text="Let me calculate that for you."),
                        ToolCallBlock(
                            type="tool_call",
                            id="call_1",
                            name="calculator",
                            input={"expression": "2 + 3 * 4"},
                        ),
                    ],
                    finish_reason="tool_use",
                )
            # 2回目の呼び出し: 最終レスポンス
            else:
                return ChatResponse(
                    content=[
                        TextBlock(type="text", text="The result of 2 + 3 * 4 is 14."),
                    ],
                    finish_reason="stop",
                )

        def parse_tool_calls(self, response):
            from amplifier_core.message_models import ToolCallBlock

            tool_calls = []
            for block in response.content:
                if isinstance(block, ToolCallBlock):
                    tool_calls.append(ToolCall(
                        tool=block.name,
                        arguments=block.input,
                        id=block.id,
                    ))
            return tool_calls

    # モック Tool
    class MockCalculatorTool:
        name = "calculator"
        description = "Performs basic calculations"

        def get_spec(self):
            from amplifier_core import ToolSpec
            return ToolSpec(
                name=self.name,
                description=self.description,
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string"},
                    },
                    "required": ["expression"],
                },
            )

        async def execute(self, input):
            from amplifier_core import ToolResult
            expr = input.get("expression", "")
            try:
                result = eval(expr)
                return ToolResult(success=True, output=result)
            except Exception as e:
                return ToolResult(success=False, error={"message": str(e)})

    # モック HookRegistry
    class MockHookRegistry:
        async def emit(self, event, data):
            logger.debug(f"Hook event: {event}")
            return None

    # セットアップ
    orchestrator = BasicLoopOrchestrator({"max_turns": 5})
    context = SimpleContextManager({})
    providers = {"mock-provider": MockProvider()}
    tools = {"calculator": MockCalculatorTool()}
    hooks = MockHookRegistry()

    # 実行
    print("Executing agent loop with mock provider...")
    print("Prompt: 'What is 2 + 3 * 4?'")
    print()

    result = await orchestrator.execute(
        prompt="What is 2 + 3 * 4?",
        context=context,
        providers=providers,
        tools=tools,
        hooks=hooks,
    )

    print(f"Final result: {result}")

    # コンテキスト確認
    messages = await context.get_messages()
    print(f"\nConversation history ({len(messages)} messages):")
    for i, msg in enumerate(messages):
        role = msg.get("role")
        content = msg.get("content", "")
        if isinstance(content, str):
            content = content[:60] + "..." if len(content) > 60 else content
        print(f"  {i+1}. [{role}]: {content}")


async def demo_with_claude_cli():
    """Claude CLI Provider との完全な統合デモ"""
    print("\n[Part 4] Claude CLI Provider との完全な統合")
    print("-" * 50)

    # Create session config
    config = {
        "session": {
            "orchestrator": "mock-orchestrator",
            "context": "mock-context",
        },
    }
    session = AmplifierSession(config)
    loader = ModuleLoader(coordinator=session.coordinator)

    # Load provider-claude-cli module
    print("Loading provider-claude-cli module...")
    provider_mount = await loader.load(
        "provider-claude-cli",
        config={"mode": "controlled"},
    )
    await provider_mount(session.coordinator)

    # Load tool-examples module
    print("Loading tool-examples module...")
    tool_mount = await loader.load(
        "tool-examples",
        config={"tools": ["calculator", "weather"]},
    )
    await tool_mount(session.coordinator)

    # Get mounted modules
    providers = session.coordinator.get("providers")
    tools = session.coordinator.get("tools")

    provider = providers.get("claude-cli")
    print(f"\nProvider: {provider.name} (mode={provider.mode})")
    print(f"Tools: {list(tools.keys())}")

    # Create orchestrator and context
    orchestrator = BasicLoopOrchestrator({
        "max_turns": 5,
        "provider": "claude-cli",
    })
    context = SimpleContextManager({})

    # Mount them manually
    await session.coordinator.mount("orchestrator", orchestrator)
    await session.coordinator.mount("context", context)

    # Execute
    print("\nExecuting agent loop...")
    print("Prompt: 'What is 123 + 456? Use the calculator tool.'")
    print()

    result = await orchestrator.execute(
        prompt="What is 123 + 456? Use the calculator tool.",
        context=context,
        providers=providers,
        tools=tools,
        hooks=session.coordinator.hooks,
        coordinator=session.coordinator,
    )

    print(f"\nFinal result:")
    print("-" * 40)
    print(result)

    await session.cleanup()


async def demo_weather_query():
    """天気クエリのデモ"""
    print("\n[Part 5] 天気クエリのデモ")
    print("-" * 50)

    config = {
        "session": {
            "orchestrator": "mock-orchestrator",
            "context": "mock-context",
        },
    }
    session = AmplifierSession(config)
    loader = ModuleLoader(coordinator=session.coordinator)

    # Load modules
    provider_mount = await loader.load(
        "provider-claude-cli",
        config={"mode": "controlled"},
    )
    await provider_mount(session.coordinator)

    tool_mount = await loader.load(
        "tool-examples",
        config={"tools": ["weather"]},
    )
    await tool_mount(session.coordinator)

    providers = session.coordinator.get("providers")
    tools = session.coordinator.get("tools")

    orchestrator = BasicLoopOrchestrator({
        "max_turns": 5,
        "provider": "claude-cli",
    })
    context = SimpleContextManager({})

    print("Prompt: 'What is the weather in Tokyo?'")
    print()

    result = await orchestrator.execute(
        prompt="What is the weather in Tokyo?",
        context=context,
        providers=providers,
        tools=tools,
        hooks=session.coordinator.hooks,
        coordinator=session.coordinator,
    )

    print(f"\nFinal result:")
    print("-" * 40)
    print(result)

    await session.cleanup()


async def demo_config_example():
    """完全な設定例のデモ"""
    print("\n[Part 6] 完全な設定例")
    print("-" * 50)

    print("""
本番環境での設定例:

config = {
    "session": {
        "orchestrator": {
            "module": "loop-basic",
            "config": {
                "max_turns": 15,
                "provider": "claude-cli",
                "temperature": 0.7,
                "max_tokens": 4096
            }
        },
        "context": {
            "module": "context-simple",
            "config": {
                "max_messages": 100,
                "compact_threshold": 80
            }
        }
    },
    "providers": [
        {
            "module": "provider-claude-cli",
            "config": {
                "mode": "controlled",
                "model": "sonnet"
            }
        }
    ],
    "tools": [
        {
            "module": "tool-examples",
            "config": {
                "tools": ["calculator", "weather"]
            }
        }
    ],
    "hooks": []
}

async with AmplifierSession(config) as session:
    result = await session.execute("What is the weather in Tokyo?")
    print(result)
""")


async def main():
    print("=" * 60)
    print("Step 4: Orchestrator の実装")
    print("=" * 60)

    await demo_orchestrator_basics()
    await demo_context_manager()
    await demo_full_loop_with_mock()

    if "--with-llm" in sys.argv:
        await demo_with_claude_cli()
        await demo_weather_query()
    else:
        print("\n" + "-" * 50)
        print("Tip: Run with --with-llm to test with Claude CLI")

    await demo_config_example()

    print("\n" + "=" * 60)
    print("Step 4 完了!")
    print("=" * 60)
    print("""
学んだこと:
  1. Orchestrator プロトコル - execute() でエージェントループを制御
  2. ContextManager プロトコル - 会話履歴の管理とコンパクション
  3. Provider と Tool の連携 - ツール仕様の生成とツール呼び出しの処理
  4. フックシステム - イベントの発行と処理

次のステップ:
  - Step 5: ContextManager の詳細実装（トークン計算、要約コンパクション）
  - Step 6: Hook システムの活用（観測性、拡張性）
  - Step 7: 統合 - 完全なエージェント
""")


if __name__ == "__main__":
    asyncio.run(main())
