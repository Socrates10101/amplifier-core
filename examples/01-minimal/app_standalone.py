"""
Example 01: 最小構成（スタンドアロン版）

Amplifier Coreの依存関係なしで動作するデモ版です。
実際の動作フローを理解するための教育的なサンプルです。
"""

import asyncio
import uuid
from typing import Any


class MockOrchestrator:
    """最もシンプルなOrchestrator実装"""

    async def execute(
        self,
        prompt: str,
        context,  # ContextManager
        providers: dict,
        tools: dict,
        hooks,  # HookRegistry
    ) -> str:
        """固定メッセージを返すだけ"""
        print(f"[DEBUG] Orchestrator.execute() called with prompt: {prompt}")

        # 最もシンプルな実装：固定メッセージを返す
        response = f"This is a mock response. Your prompt was: {prompt}"

        return response


class MockContextManager:
    """最もシンプルなContextManager実装"""

    def __init__(self):
        """メモリ内でメッセージを保持"""
        self._messages: list[dict[str, Any]] = []
        print("[DEBUG] ContextManager initialized")

    async def add_message(self, message: dict[str, Any]) -> None:
        """メッセージを追加"""
        self._messages.append(message)

    async def get_messages(self) -> list[dict[str, Any]]:
        """全メッセージを取得"""
        return self._messages.copy()

    async def should_compact(self) -> bool:
        """コンパクションは不要"""
        return False

    async def compact(self) -> None:
        """何もしない"""
        pass

    async def clear(self) -> None:
        """全メッセージをクリア"""
        self._messages.clear()


class SimpleSession:
    """AmplifierSessionの簡易版"""

    def __init__(self, config: dict):
        self.session_id = str(uuid.uuid4())
        self.config = config
        self._initialized = False

        # マウントポイント
        self.orchestrator = None
        self.context = None

        print(f"[1/3] セッション作成完了 (ID: {self.session_id})")

    async def mount_orchestrator(self, orchestrator):
        """Orchestratorをマウント"""
        self.orchestrator = orchestrator
        print("[2/3] Orchestratorをマウントしました")

    async def mount_context(self, context):
        """ContextManagerをマウント"""
        self.context = context
        print("[2/3] ContextManagerをマウントしました")

    async def initialize(self):
        """初期化"""
        if not self.orchestrator or not self.context:
            raise ValueError("Orchestrator and Context must be mounted before initialization")

        self._initialized = True
        print("[2/3] 初期化完了")

    async def execute(self, prompt: str) -> str:
        """プロンプトを実行"""
        if not self._initialized:
            raise ValueError("Session must be initialized before execution")

        print(f"[3/3] プロンプト実行: \"{prompt}\"")

        # Orchestratorに実行を委譲
        response = await self.orchestrator.execute(
            prompt=prompt,
            context=self.context,
            providers={},
            tools={},
            hooks=None,
        )

        return response


async def main():
    print("=" * 60)
    print("Example 01: 最小構成（スタンドアロン版）")
    print("=" * 60)
    print()

    print("このサンプルでは、Amplifier Coreの3つの発火ポイントを確認します：")
    print("  [1/3] AmplifierSession(config) - セッション作成")
    print("  [2/3] await session.initialize() - モジュールのマウント")
    print("  [3/3] await session.execute(prompt) - プロンプトの実行")
    print()

    # 1. セッション作成（発火ポイント1）
    config = {
        "session": {
            "orchestrator": "mock-orchestrator",
            "context": "mock-context"
        }
    }

    session = SimpleSession(config)
    print()

    # 2. モジュールをマウント（発火ポイント2）
    orchestrator = MockOrchestrator()
    await session.mount_orchestrator(orchestrator)

    context = MockContextManager()
    await session.mount_context(context)

    await session.initialize()
    print()

    # 3. プロンプトを実行（発火ポイント3）
    result = await session.execute("Hello, Amplifier!")
    print()

    print("-" * 60)
    print("レスポンス:")
    print(f"  {result}")
    print("-" * 60)
    print()

    print("=" * 60)
    print("完了")
    print("=" * 60)
    print()

    print("次のステップ:")
    print("  - 実際のamplifier-coreを使った app.py を確認")
    print("  - mock_modules.py の実装を読む")
    print("  - Example 02 でProviderを追加する")


if __name__ == "__main__":
    asyncio.run(main())
