"""
Mount function for tool-examples module.

This is the entry point called by Amplifier Core's ModuleLoader.
"""

import logging
from typing import Any, Callable, Awaitable

from amplifier_core.coordinator import ModuleCoordinator

from .tools import CalculatorTool, WeatherTool, FileReaderTool, MultiStepTool

logger = logging.getLogger(__name__)

# Available tools registry
AVAILABLE_TOOLS = {
    "calculator": CalculatorTool,
    "weather": WeatherTool,
    "file_reader": FileReaderTool,
    "multi_step": MultiStepTool,
}


async def mount(
    coordinator: ModuleCoordinator,
    config: dict[str, Any]
) -> Callable[[], Awaitable[None]] | None:
    """
    Mount example tools to the coordinator.

    Args:
        coordinator: ModuleCoordinator instance
        config: Module configuration
            - tools: List of tool names to mount (default: all)

    Returns:
        Async cleanup function or None

    Example config:
        {
            "module": "tool-examples",
            "config": {
                "tools": ["calculator", "weather"]
            }
        }
    """
    logger.info("Mounting example tools")

    # Determine which tools to mount
    tools_to_mount = config.get("tools", list(AVAILABLE_TOOLS.keys()))
    mounted_tools = []

    for tool_name in tools_to_mount:
        if tool_name not in AVAILABLE_TOOLS:
            logger.warning(f"Unknown tool: {tool_name}, skipping")
            continue

        try:
            # Create tool instance
            tool_class = AVAILABLE_TOOLS[tool_name]
            tool = tool_class()

            # Mount to coordinator
            await coordinator.mount("tools", tool, name=tool_name)
            mounted_tools.append(tool_name)

            logger.debug(f"Mounted tool: {tool_name}")

        except Exception as e:
            logger.error(f"Failed to mount tool '{tool_name}': {e}")

    logger.info(f"Mounted {len(mounted_tools)} tools: {mounted_tools}")

    # Cleanup function
    async def cleanup() -> None:
        logger.info("Cleaning up example tools")

    return cleanup
