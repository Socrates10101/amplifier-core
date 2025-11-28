"""
Step 1: 基本構造の理解

このスクリプトでは、Amplifier Coreの基本コンポーネントを学びます：
1. AmplifierSession - セッション管理
2. ModuleCoordinator - モジュール調整
3. HookRegistry - イベントシステム
"""

import asyncio

from amplifier_core import AmplifierSession
from amplifier_core.models import HookResult

from mock_modules import (
    MockOrchestrator,
    MockContextManager,
    MockProvider,
    MockTool,
)


async def main():
    print("=" * 60)
    print("Step 1: Amplifier Core 基本構造")
    print("=" * 60)

    # =========================================
    # Part 1: セッションの作成
    # =========================================
    print("\n[Part 1] セッションの作成")
    print("-" * 40)

    # 設定を定義（最低限 orchestrator と context が必要）
    config = {
        "session": {
            "orchestrator": "mock-orchestrator",
            "context": "mock-context",
        }
    }

    # セッションを作成
    session = AmplifierSession(config)
    print(f"Session ID: {session.session_id}")
    print(f"Coordinator: {type(session.coordinator).__name__}")

    # =========================================
    # Part 2: モジュールのマウント
    # =========================================
    print("\n[Part 2] モジュールのマウント")
    print("-" * 40)

    # Orchestratorをマウント
    orchestrator = MockOrchestrator()
    await session.coordinator.mount("orchestrator", orchestrator, name="mock-orchestrator")
    print("Mounted: orchestrator")

    # ContextManagerをマウント
    context = MockContextManager()
    await session.coordinator.mount("context", context, name="mock-context")
    print("Mounted: context")

    # Providerをマウント
    # mount(mount_point, module, name) の形式
    # providers/tools は複数マウント可能なので name が必要
    provider = MockProvider()
    await session.coordinator.mount("providers", provider, name="default")
    print("Mounted: providers.default")

    # Toolをマウント
    tool = MockTool()
    await session.coordinator.mount("tools", tool, name="mock-tool")
    print("Mounted: tools.mock-tool")

    # マウントされたモジュールを確認
    print("\nMounted modules:")
    print(f"  - orchestrator: {session.coordinator.get('orchestrator')}")
    print(f"  - context: {session.coordinator.get('context')}")
    providers_dict = session.coordinator.get("providers") or {}
    tools_dict = session.coordinator.get("tools") or {}
    print(f"  - providers: {list(providers_dict.keys())}")
    print(f"  - tools: {list(tools_dict.keys())}")

    # =========================================
    # Part 3: イベントシステム（Hooks）
    # =========================================
    print("\n[Part 3] イベントシステム（Hooks）")
    print("-" * 40)

    # HookRegistryを取得
    hooks = session.coordinator.hooks
    print(f"HookRegistry: {type(hooks).__name__}")

    # イベントハンドラーを登録
    event_log = []

    async def log_handler(event: str, data: dict) -> HookResult:
        """全イベントをログに記録するハンドラー"""
        event_log.append({"event": event, "data": data})
        print(f"  [Hook] Event received: {event}")
        return HookResult(action="continue")

    # 複数のイベントにハンドラーを登録
    hooks.register("prompt:submit", log_handler, priority=0, name="logger")
    hooks.register("prompt:complete", log_handler, priority=0, name="logger")
    print("Registered handlers for: prompt:submit, prompt:complete")

    # =========================================
    # Part 4: セッションの実行
    # =========================================
    print("\n[Part 4] セッションの実行")
    print("-" * 40)

    # セッションを初期化済みとしてマーク（通常は initialize() が行う）
    session._initialized = True

    # プロンプトを実行
    prompt = "Hello, Amplifier!"
    print(f"Executing: {prompt}")
    print()

    result = await session.execute(prompt)

    print()
    print(f"Result: {result}")

    # =========================================
    # Part 5: イベントログの確認
    # =========================================
    print("\n[Part 5] イベントログの確認")
    print("-" * 40)

    print(f"Total events captured: {len(event_log)}")
    for i, entry in enumerate(event_log):
        print(f"  {i + 1}. {entry['event']}")

    # =========================================
    # クリーンアップ
    # =========================================
    print("\n[Cleanup]")
    print("-" * 40)
    await session.cleanup()
    print("Session cleaned up")

    print("\n" + "=" * 60)
    print("Step 1 完了!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
