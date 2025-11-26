"""
Mock modules for minimal example.

These are the simplest possible implementations of Orchestrator and ContextManager.
"""

import logging
from typing import Any

from amplifier_core.coordinator import ModuleCoordinator

logger = logging.getLogger(__name__)


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
        logger.info(f"Orchestrator received prompt: {prompt}")

        # 最もシンプルな実装：固定メッセージを返す
        response = f"This is a mock response. Your prompt was: {prompt}"

        return response


class MockContextManager:
    """最もシンプルなContextManager実装"""

    def __init__(self):
        """メモリ内でメッセージを保持"""
        self._messages: list[dict[str, Any]] = []

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


# === モジュールエントリーポイント ===

async def mount_orchestrator(coordinator: ModuleCoordinator, config: dict):
    """MockOrchestratorをマウント"""
    logger.info("Loading orchestrator: mock-orchestrator")

    orchestrator = MockOrchestrator()

    # Coordinatorに登録
    await coordinator.mount("orchestrator", orchestrator, name="mock-orchestrator")

    logger.info("Mock orchestrator mounted successfully")
    return None  # cleanup function (オプション)


async def mount_context(coordinator: ModuleCoordinator, config: dict):
    """MockContextManagerをマウント"""
    logger.info("Loading context manager: mock-context")

    context = MockContextManager()

    # Coordinatorに登録
    await coordinator.mount("context", context, name="mock-context")

    logger.info("Mock context manager mounted successfully")
    return None  # cleanup function (オプション)
