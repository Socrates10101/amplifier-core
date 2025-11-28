"""
Mount functions for step4-orchestrator modules.

Amplifier Core のモジュール規約に従った mount() 関数を提供します。
"""

import logging
from typing import Any, Callable, Awaitable

from amplifier_core.coordinator import ModuleCoordinator

from .orchestrator import BasicLoopOrchestrator
from .context import SimpleContextManager

logger = logging.getLogger(__name__)


async def mount_orchestrator(
    coordinator: ModuleCoordinator,
    config: dict[str, Any],
) -> Callable[[], Awaitable[None]] | None:
    """
    Basic Loop Orchestrator を Coordinator にマウント。

    Args:
        coordinator: ModuleCoordinator インスタンス
        config: モジュール設定
            - max_turns: 最大ターン数（デフォルト: 10）
            - provider: 使用するプロバイダー名
            - temperature: 温度パラメータ（デフォルト: 0.7）
            - max_tokens: 最大トークン数（デフォルト: 4096）

    Returns:
        クリーンアップ関数（または None）

    Example:
        loader = ModuleLoader(coordinator=session.coordinator)
        mount_fn = await loader.load("loop-basic", config={"max_turns": 15})
        await mount_fn(session.coordinator)
    """
    logger.info("Mounting Basic Loop Orchestrator")

    # インスタンス作成
    orchestrator = BasicLoopOrchestrator(config)

    # Coordinator にマウント
    await coordinator.mount("orchestrator", orchestrator)

    logger.info("Basic Loop Orchestrator mounted successfully")

    # クリーンアップ関数
    async def cleanup() -> None:
        logger.info("Cleaning up Basic Loop Orchestrator")

    return cleanup


async def mount_context(
    coordinator: ModuleCoordinator,
    config: dict[str, Any],
) -> Callable[[], Awaitable[None]] | None:
    """
    Simple Context Manager を Coordinator にマウント。

    Args:
        coordinator: ModuleCoordinator インスタンス
        config: モジュール設定
            - max_messages: 最大メッセージ数（デフォルト: 100）
            - compact_threshold: コンパクション閾値（デフォルト: 80）
            - keep_system: システムメッセージを保持（デフォルト: True）
            - keep_recent: コンパクト時に保持する最近のメッセージ数（デフォルト: 20）

    Returns:
        クリーンアップ関数（または None）

    Example:
        loader = ModuleLoader(coordinator=session.coordinator)
        mount_fn = await loader.load("context-simple", config={"max_messages": 50})
        await mount_fn(session.coordinator)
    """
    logger.info("Mounting Simple Context Manager")

    # インスタンス作成
    context = SimpleContextManager(config)

    # Coordinator にマウント
    await coordinator.mount("context", context)

    logger.info("Simple Context Manager mounted successfully")

    # クリーンアップ関数
    async def cleanup() -> None:
        logger.info("Cleaning up Simple Context Manager")
        await context.clear()

    return cleanup
