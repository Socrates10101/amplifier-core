"""
Example 01: 最小構成

最もシンプルなAmplifier Coreの実装例です。
モックコンポーネントを使用して、基本的な動作フローを確認します。
"""

import asyncio
import logging

from amplifier_core import AmplifierSession

# Import mock modules directly
from mock_modules import MockOrchestrator, MockContextManager

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)

async def main():
    print("=== Example 01: 最小構成 ===\n")

    # 1. セッション作成（発火ポイント1）
    print("[INFO] Creating AmplifierSession...")

    # 設定は必須だが、モジュールIDは使わない
    # （直接マウントするため）
    config = {
        "session": {
            "orchestrator": "mock-orchestrator",  # 識別用（実際には使われない）
            "context": "mock-context"  # 識別用（実際には使われない）
        }
    }

    session = AmplifierSession(config)
    print(f"[INFO] Session ID: {session.session_id}\n")

    # 2. モジュールを直接マウント（通常は initialize() が行う）
    print("[INFO] Mounting mock modules directly...")

    # Orchestratorをマウント
    orchestrator = MockOrchestrator()
    await session.coordinator.mount("orchestrator", orchestrator, name="mock-orchestrator")
    print("[INFO] - Orchestrator mounted")

    # ContextManagerをマウント
    context = MockContextManager()
    await session.coordinator.mount("context", context, name="mock-context")
    print("[INFO] - Context manager mounted\n")

    # セッションを初期化済みとしてマーク
    session._initialized = True

    # 3. プロンプトを実行（発火ポイント3）
    print("[INFO] Executing prompt: \"Hello, Amplifier!\"")
    result = await session.execute("Hello, Amplifier!")

    print(f"[INFO] Response: {result}\n")

    print("=== Done ===")

    # クリーンアップ
    await session.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
