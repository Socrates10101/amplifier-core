"""
Mount function for provider-claude-cli module.

This is the entry point called by Amplifier Core's ModuleLoader.
Follows the standard Amplifier module mount signature:

    async def mount(coordinator: ModuleCoordinator, config: dict) -> Callable | None
"""

import logging
from typing import Any, Callable, Awaitable

from amplifier_core.coordinator import ModuleCoordinator

from .provider import ClaudeCliProvider

logger = logging.getLogger(__name__)


async def mount(
    coordinator: ModuleCoordinator,
    config: dict[str, Any]
) -> Callable[[], Awaitable[None]] | None:
    """
    Mount Claude CLI Provider to the coordinator.

    This function follows the Amplifier Core module mount contract:
    - Receives coordinator and config
    - Creates and mounts the provider instance
    - Returns optional cleanup function

    Args:
        coordinator: ModuleCoordinator instance
        config: Module configuration
            - mode: "passthrough" or "controlled" (default: "controlled")
            - model: Model name (e.g., "sonnet", "opus")
            - timeout: Timeout in seconds (default: 300)
            - name: Provider name (default: "claude-cli")

    Returns:
        Async cleanup function or None

    Example config:
        {
            "module": "provider-claude-cli",
            "config": {
                "mode": "controlled",
                "model": "sonnet",
                "timeout": 300
            }
        }
    """
    logger.info("Mounting Claude CLI Provider")

    try:
        # Create provider instance
        provider = ClaudeCliProvider(config)

        # Get provider name from config or use default
        provider_name = config.get("name", "claude-cli")

        # Mount to coordinator's providers mount point
        await coordinator.mount("providers", provider, name=provider_name)

        # Register metrics contributor if coordinator supports it
        if hasattr(coordinator, "register_contributor"):
            coordinator.register_contributor(
                "metrics.providers",
                f"provider-{provider_name}",
                lambda p=provider: {
                    "name": p.name,
                    "mode": p.mode,
                    "version": p.version,
                    "requests": p.request_count,
                    "total_duration_ms": p.total_duration_ms,
                }
            )

        logger.info(
            f"Claude CLI Provider mounted as '{provider_name}' "
            f"(mode={provider.mode}, version={provider.version})"
        )

        # Cleanup function
        async def cleanup() -> None:
            logger.info(f"Cleaning up Claude CLI Provider '{provider_name}'")
            # Claude CLI is stateless, no cleanup needed
            # But we follow the pattern for consistency

        return cleanup

    except Exception as e:
        logger.error(f"Failed to mount Claude CLI Provider: {e}")
        raise
