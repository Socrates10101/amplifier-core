"""
Step 5: ContextManager の詳細実装

このスクリプトでは、高度なコンテキスト管理を学びます：
1. トークン計算の仕組み
2. 要約コンパクションの実装
3. 重要度ベースのメッセージ保持
4. Orchestrator との統合

実行方法:
    python app.py              # 基本デモ
    python app.py --with-llm   # Claude CLI 統合デモ（要約コンパクション使用）
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

from context import AdvancedContextManager
from tokenizer import TokenCounter, TokenBudget

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def demo_token_counter():
    """TokenCounter の基本デモ"""
    print("\n[Part 1] TokenCounter の基本")
    print("-" * 50)

    # TokenCounter の作成
    counter = TokenCounter(method="auto")
    print(f"TokenCounter method: {counter.method}")

    # テキストのトークン数を計算
    test_texts = [
        "Hello, world!",
        "The quick brown fox jumps over the lazy dog.",
        "日本語のテキストもトークン数を計算できます。",
        "def calculate(a, b):\n    return a + b",
    ]

    print("\nToken counts:")
    for text in test_texts:
        count = counter.count(text)
        print(f"  '{text[:30]}{'...' if len(text) > 30 else ''}': {count} tokens")

    # メッセージのトークン数を計算
    print("\nMessage token counts:")
    messages = [
        {"role": "user", "content": "What is 2 + 2?"},
        {"role": "assistant", "content": "2 + 2 = 4. This is a basic arithmetic operation."},
        {"role": "tool", "content": "Result: 4", "tool_call_id": "call_001"},
    ]

    for msg in messages:
        count = counter.count_message(msg)
        role = msg.get("role")
        content = str(msg.get("content", ""))[:30]
        print(f"  [{role}] '{content}...': {count} tokens")


async def demo_token_budget():
    """TokenBudget の基本デモ"""
    print("\n[Part 2] TokenBudget の基本")
    print("-" * 50)

    # TokenBudget の作成
    budget = TokenBudget(
        max_tokens=1000,
        warning_threshold=0.8,
        compact_threshold=0.75,
    )

    print(f"Initial state:")
    print(f"  Max tokens: {budget.max_tokens}")
    print(f"  Current tokens: {budget.current_tokens}")
    print(f"  Usage: {budget.usage_percentage:.1%}")

    # トークンを追加
    print("\nAdding tokens...")
    budget.add(300)
    print(f"  After adding 300: {budget.current_tokens} ({budget.usage_percentage:.1%})")

    budget.add(500)
    print(f"  After adding 500: {budget.current_tokens} ({budget.usage_percentage:.1%})")

    # 状態チェック
    print(f"\nStatus checks:")
    print(f"  Should warn: {budget.should_warn()}")
    print(f"  Should compact: {budget.should_compact()}")
    print(f"  Is exceeded: {budget.is_exceeded()}")

    # 予算超過
    budget.add(300)
    print(f"\n  After adding 300 more: {budget.current_tokens} ({budget.usage_percentage:.1%})")
    print(f"  Is exceeded: {budget.is_exceeded()}")


async def demo_context_manager_basics():
    """AdvancedContextManager の基本デモ"""
    print("\n[Part 3] AdvancedContextManager の基本")
    print("-" * 50)

    # AdvancedContextManager の作成
    context = AdvancedContextManager({
        "max_tokens": 500,
        "compact_threshold": 300,
        "keep_recent": 3,
        "use_summary": False,  # 基本デモでは要約なし
    })

    print(f"AdvancedContextManager created:")
    print(f"  Max tokens: 500")
    print(f"  Compact threshold: 300")
    print(f"  Keep recent: 3")

    # システムプロンプトを追加
    await context.add_system_prompt("You are a helpful assistant.")

    # メッセージを追加
    print("\nAdding messages...")
    test_messages = [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there! How can I help you today?"},
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
        {"role": "user", "content": "Tell me more about Paris."},
        {"role": "assistant", "content": "Paris is the largest city in France and serves as the country's capital. It's known for the Eiffel Tower, the Louvre Museum, and its rich cultural heritage."},
        {"role": "user", "content": "What about Tokyo?"},
        {"role": "assistant", "content": "Tokyo is the capital of Japan and one of the most populous cities in the world. It's a fascinating blend of traditional and modern culture."},
    ]

    for msg in test_messages:
        await context.add_message(msg)
        stats = context.get_stats()
        print(f"  Added {msg['role']} message: {stats['total_tokens']} tokens")

    # 統計情報
    stats = context.get_stats()
    print(f"\nContext statistics:")
    print(f"  Message count: {stats['message_count']}")
    print(f"  Total tokens: {stats['total_tokens']}")
    print(f"  Usage: {stats['usage_percentage']:.1%}")

    # コンパクション判定
    should_compact = await context.should_compact()
    print(f"\nShould compact: {should_compact}")

    if should_compact:
        print("\nPerforming compaction...")
        await context.compact()

        stats = context.get_stats()
        print(f"\nAfter compaction:")
        print(f"  Message count: {stats['message_count']}")
        print(f"  Total tokens: {stats['total_tokens']}")
        print(f"  Compact count: {stats['compact_count']}")

        # コンパクション後のメッセージを表示
        messages = await context.get_messages()
        print(f"\nMessages after compaction:")
        for i, msg in enumerate(messages):
            role = msg.get("role")
            content = str(msg.get("content", ""))[:50]
            print(f"  {i+1}. [{role}]: {content}...")


async def demo_important_message_retention():
    """重要度ベースのメッセージ保持デモ"""
    print("\n[Part 4] 重要度ベースのメッセージ保持")
    print("-" * 50)

    context = AdvancedContextManager({
        "max_tokens": 500,
        "compact_threshold": 300,
        "keep_recent": 2,
        "use_summary": False,
    })

    # 重要なメッセージを含む会話
    messages = [
        {"role": "user", "content": "Calculate 100 * 5"},
        {"role": "assistant", "content": "Let me calculate that for you."},
        {"role": "tool", "content": "500", "tool_call_id": "call_001"},  # 重要: ツール結果
        {"role": "assistant", "content": "The result is 500."},
        {"role": "user", "content": "Now try something that fails"},
        {"role": "assistant", "content": "[Error: Invalid operation]"},  # 重要: エラー
        {"role": "user", "content": "One more question"},
        {"role": "assistant", "content": "Sure, what would you like to know?"},
        {"role": "user", "content": "What is the weather?"},
        {"role": "assistant", "content": "I don't have access to weather information."},
    ]

    print("Adding messages with important ones (tool results, errors)...")
    for msg in messages:
        await context.add_message(msg)

    print(f"\nBefore compaction:")
    print(f"  Message count: {context.message_count}")
    print(f"  Total tokens: {context.total_tokens}")

    # コンパクション
    if await context.should_compact():
        await context.compact()

        print(f"\nAfter compaction:")
        print(f"  Message count: {context.message_count}")

        result_messages = await context.get_messages()
        print("\nRetained messages:")
        for i, msg in enumerate(result_messages):
            role = msg.get("role")
            content = str(msg.get("content", ""))[:60]
            is_tool = role == "tool"
            is_error = "error" in content.lower()
            marker = " [IMPORTANT]" if is_tool or is_error else ""
            print(f"  {i+1}. [{role}]: {content}...{marker}")


async def demo_summary_compaction():
    """要約コンパクションのデモ（Claude CLI 統合）"""
    print("\n[Part 5] 要約コンパクション（Claude CLI 統合）")
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

    # Get provider
    providers = session.coordinator.get("providers")
    provider = providers.get("claude-cli")
    print(f"Provider: {provider.name}")

    # Create AdvancedContextManager with summary enabled
    context = AdvancedContextManager({
        "max_tokens": 1000,
        "compact_threshold": 600,
        "keep_recent": 3,
        "use_summary": True,
        "summary_max_tokens": 200,
    })

    # Set summary provider
    context.set_summary_provider(provider)

    # Add many messages to trigger compaction
    print("\nAdding messages to trigger compaction...")
    long_messages = [
        {"role": "user", "content": "Hello! I'm interested in learning about programming."},
        {"role": "assistant", "content": "Great! Programming is a wonderful skill to learn. There are many languages to choose from, such as Python, JavaScript, Java, and many others. What aspects of programming are you most interested in?"},
        {"role": "user", "content": "I'd like to learn about web development."},
        {"role": "assistant", "content": "Web development is an excellent choice! It involves creating websites and web applications. You'll typically learn HTML for structure, CSS for styling, and JavaScript for interactivity. There are also many frameworks and libraries to explore."},
        {"role": "user", "content": "What about backend development?"},
        {"role": "assistant", "content": "Backend development handles the server-side logic of web applications. Popular technologies include Node.js, Python with Django or Flask, Ruby on Rails, and Java with Spring. You'll also learn about databases, APIs, and server management."},
        {"role": "user", "content": "Can you recommend a learning path?"},
        {"role": "assistant", "content": "Certainly! I recommend starting with HTML and CSS basics, then moving to JavaScript. Once comfortable, learn a frontend framework like React or Vue.js. For backend, start with Node.js or Python. Practice building full-stack projects to reinforce your learning."},
        {"role": "user", "content": "Thank you! Any final tips?"},
        {"role": "assistant", "content": "Build projects regularly, contribute to open source, join developer communities, and never stop learning. The tech field evolves quickly, so staying curious and adaptable is key to success!"},
    ]

    for msg in long_messages:
        await context.add_message(msg)
        print(f"  Added message: {context.total_tokens} tokens")

    print(f"\nBefore compaction:")
    print(f"  Message count: {context.message_count}")
    print(f"  Total tokens: {context.total_tokens}")

    # Perform compaction
    if await context.should_compact():
        print("\nPerforming summary compaction...")
        await context.compact()

        print(f"\nAfter compaction:")
        print(f"  Message count: {context.message_count}")
        print(f"  Total tokens: {context.total_tokens}")

        # Show compacted messages
        result_messages = await context.get_messages()
        print("\nCompacted messages:")
        for i, msg in enumerate(result_messages):
            role = msg.get("role")
            content = str(msg.get("content", ""))
            is_summary = "[Previous conversation summary]" in content or "[summary]" in content.lower()

            if is_summary:
                print(f"\n  {i+1}. [{role}] [SUMMARY]:")
                # Print summary content with indentation
                for line in content.split("\n"):
                    print(f"      {line[:80]}{'...' if len(line) > 80 else ''}")
            else:
                print(f"\n  {i+1}. [{role}]: {content[:100]}{'...' if len(content) > 100 else ''}")

    await session.cleanup()


async def demo_with_orchestrator():
    """Orchestrator との統合デモ"""
    print("\n[Part 6] Orchestrator との統合")
    print("-" * 50)

    # Import step4 orchestrator
    from step4_orchestrator.orchestrator import BasicLoopOrchestrator

    # Create session
    config = {
        "session": {
            "orchestrator": "mock-orchestrator",
            "context": "mock-context",
        },
    }
    session = AmplifierSession(config)
    loader = ModuleLoader(coordinator=session.coordinator)

    # Load modules
    print("Loading modules...")
    provider_mount = await loader.load(
        "provider-claude-cli",
        config={"mode": "controlled"},
    )
    await provider_mount(session.coordinator)

    tool_mount = await loader.load(
        "tool-examples",
        config={"tools": ["calculator", "weather"]},
    )
    await tool_mount(session.coordinator)

    # Get mounted modules
    providers = session.coordinator.get("providers")
    tools = session.coordinator.get("tools")

    print(f"Provider: {list(providers.keys())}")
    print(f"Tools: {list(tools.keys())}")

    # Create AdvancedContextManager
    context = AdvancedContextManager({
        "max_tokens": 4000,
        "compact_threshold": 3000,
        "keep_recent": 5,
        "use_summary": True,
    })

    # Set summary provider
    context.set_summary_provider(providers.get("claude-cli"))

    # Mount context
    await session.coordinator.mount("context", context)

    # Create orchestrator
    orchestrator = BasicLoopOrchestrator({
        "max_turns": 5,
        "provider": "claude-cli",
    })

    # Execute a query
    print("\nExecuting query: 'What is 123 + 456? Use the calculator.'")
    result = await orchestrator.execute(
        prompt="What is 123 + 456? Use the calculator.",
        context=context,
        providers=providers,
        tools=tools,
        hooks=session.coordinator.hooks,
        coordinator=session.coordinator,
    )

    print(f"\nResult: {result[:200]}...")

    # Show context statistics
    stats = context.get_stats()
    print(f"\nContext statistics after execution:")
    print(f"  Message count: {stats['message_count']}")
    print(f"  Total tokens: {stats['total_tokens']}")
    print(f"  Usage: {stats['usage_percentage']:.1%}")

    await session.cleanup()


async def main():
    print("=" * 60)
    print("Step 5: ContextManager の詳細実装")
    print("=" * 60)

    await demo_token_counter()
    await demo_token_budget()
    await demo_context_manager_basics()
    await demo_important_message_retention()

    if "--with-llm" in sys.argv:
        await demo_summary_compaction()
        await demo_with_orchestrator()
    else:
        print("\n" + "-" * 50)
        print("Tip: Run with --with-llm to test summary compaction with Claude CLI")

    print("\n" + "=" * 60)
    print("Step 5 完了!")
    print("=" * 60)
    print("""
学んだこと:
  1. TokenCounter - トークン数の正確な計算
  2. TokenBudget - トークン予算の管理
  3. AdvancedContextManager - 高度なコンテキスト管理
  4. 要約コンパクション - LLM を使った会話の要約
  5. 重要度ベース保持 - ツール結果やエラーの優先保持

次のステップ:
  - Step 6: Hook システムの活用（観測性、拡張性）
  - Step 7: 統合 - 完全なエージェント
""")


if __name__ == "__main__":
    asyncio.run(main())
