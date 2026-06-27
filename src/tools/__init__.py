"""Unified graph-facing tool system."""

from src.tools.catalog import ToolCatalog, ToolDescriptor
from src.tools.contracts import ToolCallContext, ToolError, ToolRequest, ToolResultV2


def __getattr__(name: str):
    if name == "UnifiedToolManager":
        from src.tools.manager import UnifiedToolManager

        return UnifiedToolManager
    raise AttributeError(name)

__all__ = [
    "ToolCallContext",
    "ToolCatalog",
    "ToolDescriptor",
    "ToolError",
    "ToolRequest",
    "ToolResultV2",
    "UnifiedToolManager",
]
