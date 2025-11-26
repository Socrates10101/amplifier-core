"""
Step 3: Toolの実装

このスクリプトでは、エージェントが使用できるツールの仕組みを学びます：
1. Toolプロトコルの理解
2. ToolCall / ToolResult の構造
3. Amplifier Core のモジュールローディング
4. Claude CLI Provider との統合

実行方法:
    python app.py              # 基本デモ
    python app.py --with-llm   # Claude CLI との統合デモ
"""

import asyncio
import sys
from pathlib import Path

# Add examples directory to path for module discovery
# In production, modules would be installed via pip or entry points
sys.path.insert(0, str(Path(__file__).parent.parent))

from amplifier_core import AmplifierSession
from amplifier_core.models import ToolCall
from amplifier_core.message_models import ChatRequest, Message, TextBlock
from amplifier_core.loader import ModuleLoader
from amplifier_core.coordinator import ModuleCoordinator


async def demo_tool_basics():
    """Tool プロトコルの基本デモ"""
    print("\n[Part 1] Tool プロトコルの基本")
    print("-" * 40)

    # Import tools directly for demonstration
    from amplifier_module_tool_examples import CalculatorTool

    calculator = CalculatorTool()

    print(f"Tool name: {calculator.name}")
    print(f"Tool description: {calculator.description}")

    # ToolCall の作成（通常は LLM が生成）
    tool_call = ToolCall(
        tool="calculator",
        arguments={"expression": "2 + 3 * 4"},
        id="call_001"
    )

    print(f"\nToolCall:")
    print(f"  tool: {tool_call.tool}")
    print(f"  arguments: {tool_call.arguments}")

    # 実行
    result = await calculator.execute(tool_call.arguments)
    print(f"\nToolResult:")
    print(f"  success: {result.success}")
    print(f"  output: {result.output}")


async def demo_module_loading():
    """Amplifier Core のモジュールローディングデモ"""
    print("\n[Part 2] モジュールローディング")
    print("-" * 40)

    # Create a minimal session config
    config = {
        "session": {
            "orchestrator": "mock-orchestrator",
            "context": "mock-context",
        }
    }
    session = AmplifierSession(config)

    # Load tool-examples module using ModuleLoader
    loader = ModuleLoader(coordinator=session.coordinator)

    # Load and mount the tool-examples module
    tool_mount = await loader.load(
        "tool-examples",
        config={"tools": ["calculator", "weather", "file_reader"]}
    )
    await tool_mount(session.coordinator)

    # Verify mounted tools
    tools = session.coordinator.get("tools")
    print(f"Mounted tools: {list(tools.keys())}")

    # Execute tools via coordinator
    print("\nExecuting tools:")
    for name, tool in tools.items():
        if name == "calculator":
            result = await tool.execute({"expression": "100 * 5"})
            print(f"  calculator: 100 * 5 = {result.output}")
        elif name == "weather":
            result = await tool.execute({"city": "Tokyo"})
            print(f"  weather: Tokyo = {result.output['condition']}, {result.output['temperature']}°C")

    await session.cleanup()


async def demo_with_claude_cli():
    """Claude CLI Provider との統合デモ"""
    print("\n[Part 3] Claude CLI Provider との統合")
    print("-" * 40)

    # Create session config with Claude CLI provider
    config = {
        "session": {
            "orchestrator": "mock-orchestrator",
            "context": "mock-context",
        }
    }
    session = AmplifierSession(config)
    loader = ModuleLoader(coordinator=session.coordinator)

    # Load provider-claude-cli module
    provider_mount = await loader.load(
        "provider-claude-cli",
        config={"mode": "controlled"}
    )
    await provider_mount(session.coordinator)

    # Load tool-examples module
    tool_mount = await loader.load(
        "tool-examples",
        config={"tools": ["calculator", "weather"]}
    )
    await tool_mount(session.coordinator)

    # Get mounted modules
    providers = session.coordinator.get("providers")
    tools = session.coordinator.get("tools")

    provider = providers.get("claude-cli")
    print(f"Provider: {provider.name} (mode={provider.mode})")
    print(f"Tools: {list(tools.keys())}")

    # Create tool specs for LLM
    tool_specs = [tools[name].get_spec() for name in tools]

    # Test: Calculation request
    print("\n--- Calculation Request ---")
    request = ChatRequest(
        messages=[
            Message(
                role="user",
                content=[TextBlock(
                    type="text",
                    text="What is 456 + 789 * 2? Use the calculator tool."
                )]
            )
        ],
        tools=tool_specs,
    )

    response = await provider.complete(request)
    print(f"finish_reason: {response.finish_reason}")

    # Process tool calls
    tool_calls = provider.parse_tool_calls(response)
    if tool_calls:
        for tc in tool_calls:
            print(f"Tool call: {tc.tool}({tc.arguments})")

            tool = tools.get(tc.tool)
            if tool:
                result = await tool.execute(tc.arguments)
                print(f"Result: {result.output}")

                # Follow-up with result
                messages = list(request.messages)
                messages.append(Message(role="assistant", content=response.content))
                messages.append(Message(
                    role="tool",
                    content=[TextBlock(type="text", text=f"Result: {result.output}")]
                ))

                follow_up = ChatRequest(messages=messages, tools=tool_specs)
                final = await provider.complete(follow_up)

                for block in final.content:
                    if isinstance(block, TextBlock):
                        text = block.text[:200] + "..." if len(block.text) > 200 else block.text
                        print(f"Final: {text}")
    else:
        for block in response.content:
            if isinstance(block, TextBlock):
                print(f"Response: {block.text[:150]}")

    await session.cleanup()


async def demo_full_config():
    """完全な設定例のデモ"""
    print("\n[Part 4] 完全な設定例")
    print("-" * 40)

    print("""
本番環境での設定例:

config = {
    "session": {
        "orchestrator": "loop-basic",
        "context": "context-simple"
    },
    "providers": [
        {
            "module": "provider-claude-cli",
            "config": {
                "mode": "controlled",
                "model": "sonnet",
                "timeout": 300
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
    result = await session.execute("What is 2+2?")
    print(result)
""")


async def main():
    print("=" * 60)
    print("Step 3: Tool の実装")
    print("=" * 60)

    await demo_tool_basics()
    await demo_module_loading()

    if "--with-llm" in sys.argv:
        await demo_with_claude_cli()
    else:
        print("\n" + "-" * 40)
        print("Tip: Run with --with-llm to test with Claude CLI")

    await demo_full_config()

    print("\n" + "=" * 60)
    print("Step 3 完了!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
