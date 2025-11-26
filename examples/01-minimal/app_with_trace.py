"""
Example 01: 最小構成（トレース版）

3つの発火ポイントを視覚的に表示します。
"""

import asyncio
import uuid


class SimpleTracer:
    """シンプルなトレーサー"""

    def __init__(self):
        self.step = 0

    def step_start(self, title: str):
        """ステップ開始"""
        self.step += 1
        print(f"\n{'═' * 60}")
        print(f"  発火ポイント {self.step}/3: {title}")
        print(f"{'═' * 60}\n")

    def log(self, message: str):
        """ログ"""
        print(f"  → {message}")


tracer = SimpleTracer()


class MockOrchestrator:
    """最もシンプルなOrchestrator実装"""

    async def execute(self, prompt: str, context, providers: dict, tools: dict, hooks) -> str:
        """固定メッセージを返すだけ"""
        tracer.log(f"Orchestrator.execute() が呼ばれました")
        tracer.log(f"プロンプト: '{prompt}'")
        tracer.log(f"処理中...")

        response = f"This is a mock response. Your prompt was: {prompt}"

        tracer.log(f"レスポンス生成: '{response[:40]}...'")
        return response


class MockContextManager:
    """最もシンプルなContextManager実装"""

    def __init__(self):
        self._messages = []
        tracer.log("ContextManager インスタンス生成")

    async def add_message(self, message: dict) -> None:
        self._messages.append(message)

    async def get_messages(self) -> list[dict]:
        return self._messages.copy()

    async def should_compact(self) -> bool:
        return False

    async def compact(self) -> None:
        pass

    async def clear(self) -> None:
        self._messages.clear()


class SimpleSession:
    """AmplifierSessionの簡易版"""

    def __init__(self, config: dict):
        self.session_id = str(uuid.uuid4())
        self.config = config
        self._initialized = False

        self.orchestrator = None
        self.context = None

        tracer.log(f"Session インスタンス生成")
        tracer.log(f"Session ID: {self.session_id[:8]}...")

    async def mount_orchestrator(self, orchestrator):
        self.orchestrator = orchestrator
        tracer.log("Orchestrator をマウント")

    async def mount_context(self, context):
        self.context = context
        tracer.log("ContextManager をマウント")

    async def initialize(self):
        if not self.orchestrator or not self.context:
            raise ValueError("Orchestrator and Context required")

        self._initialized = True
        tracer.log("初期化完了 ✓")

    async def execute(self, prompt: str) -> str:
        if not self._initialized:
            raise ValueError("Not initialized")

        tracer.log(f"Session.execute() が呼ばれました")
        tracer.log(f"プロンプト: '{prompt}'")

        response = await self.orchestrator.execute(
            prompt=prompt,
            context=self.context,
            providers={},
            tools={},
            hooks=None,
        )

        tracer.log("実行完了 ✓")
        return response


async def main():
    print("=" * 60)
    print("Example 01: 最小構成（トレース版）")
    print("=" * 60)
    print()
    print("Amplifier Coreの3つの発火ポイントを追跡します：")
    print()

    # === 発火ポイント 1: セッション作成 ===
    tracer.step_start("AmplifierSession(config)")

    config = {
        "session": {
            "orchestrator": "mock-orchestrator",
            "context": "mock-context"
        }
    }

    session = SimpleSession(config)

    # === 発火ポイント 2: 初期化（モジュールマウント） ===
    tracer.step_start("await session.initialize()")

    orchestrator = MockOrchestrator()
    await session.mount_orchestrator(orchestrator)

    context = MockContextManager()
    await session.mount_context(context)

    await session.initialize()

    # === 発火ポイント 3: プロンプト実行 ===
    tracer.step_start("await session.execute(prompt)")

    result = await session.execute("Hello, Amplifier!")

    # 結果表示
    print()
    print("=" * 60)
    print("  最終結果")
    print("=" * 60)
    print()
    print(f"  {result}")
    print()
    print("=" * 60)
    print()
    print("学んだこと:")
    print("  1. AmplifierSession(config) でセッションを作成")
    print("  2. await session.initialize() でモジュールをマウント")
    print("  3. await session.execute(prompt) でプロンプトを実行")
    print()
    print("次のステップ:")
    print("  → Example 02 でProviderを追加")
    print()


if __name__ == "__main__":
    asyncio.run(main())
