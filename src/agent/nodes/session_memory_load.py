from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from src.agent.nodes.session_context_load import session_context_load
from src.agent.state import AgentState
from src.config import settings
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.memory.context_service import MemoryContextService
from src.memory.repository import SessionMemoryRepository
from src.memory.session_bundle import SessionMemoryBundleService
from src.memory.service import MemoryService


async def session_memory_load(state: AgentState, config: RunnableConfig) -> dict:
    """Compatibility wrapper for the target session_context_load node."""
    return await session_context_load(
        state,
        config,
        node_name="session_memory_load",
        settings_obj=settings,
        memory_service_cls=MemoryService,
        session_memory_repository_cls=SessionMemoryRepository,
        session_memory_bundle_service_cls=SessionMemoryBundleService,
        conversation_repository_cls=ConversationRepository,
        conversation_service_cls=ConversationService,
        memory_context_service_cls=MemoryContextService,
    )
