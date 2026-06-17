from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


BlockName = Literal[
    "system_prompt",
    "current_user_message",
    "safety_constraints",
    "business_ids",
    "policy_refs",
    "profile_memory",
    "case_memory",
    "working_state",
    "business_context",
    "thread_rolling_summary",
    "recent_messages",
    "tool_summaries",
    "node_hints",
    "old_recent_messages",
    "verbose_tool_summaries",
    "extra_policy_snippets",
    "low_value_summary_details",
]

PROTECTED_BLOCK_NAMES = frozenset(
    {
        "system_prompt",
        "current_user_message",
        "safety_constraints",
        "business_ids",
        "policy_refs",
    }
)
LOW_PRIORITY_TRUNCATION_ORDER = (
    "old_recent_messages",
    "verbose_tool_summaries",
    "extra_policy_snippets",
    "low_value_summary_details",
)
TRUNCATION_MARKER = "\n[block_truncated]"


@dataclass(frozen=True)
class PromptBlock:
    name: str
    content: str
    priority: int = 50
    protected: bool = False

    def normalized(self) -> "PromptBlock":
        return PromptBlock(
            name=self.name,
            content=" ".join(self.content.split()) if "\n" not in self.content else self.content.strip(),
            priority=self.priority,
            protected=self.protected or self.name in PROTECTED_BLOCK_NAMES,
        )


@dataclass(frozen=True)
class PromptAssembly:
    blocks: tuple[PromptBlock, ...]
    omitted_block_names: tuple[str, ...] = field(default_factory=tuple)
    max_chars: int | None = None

    @property
    def protected_blocks(self) -> tuple[PromptBlock, ...]:
        return tuple(block for block in self.blocks if block.protected)

    @property
    def non_system_blocks(self) -> tuple[PromptBlock, ...]:
        return tuple(block for block in self.blocks if block.name != "system_prompt")

    def to_messages(self) -> list[dict[str, str]]:
        system_content = ""
        user_parts: list[str] = []
        for block in self.blocks:
            if block.name == "system_prompt":
                system_content = block.content
                continue
            user_parts.append(f"[{block.name}]\n{block.content}")

        messages: list[dict[str, str]] = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        if user_parts:
            messages.append({"role": "user", "content": "\n\n".join(user_parts)})
        return messages

    def user_content(self) -> str:
        return "\n\n".join(f"[{block.name}]\n{block.content}" for block in self.non_system_blocks)


class TokenBudgetPolicy:
    def __init__(self, max_chars: int = 8000) -> None:
        self.max_chars = max_chars

    def apply(self, blocks: list[PromptBlock] | tuple[PromptBlock, ...]) -> PromptAssembly:
        normalized = [block.normalized() for block in blocks if block.content.strip()]
        kept = list(normalized)
        omitted: list[str] = []

        while _total_chars(kept) > self.max_chars:
            candidate_index = _lowest_value_candidate_index(kept)
            if candidate_index is None:
                break
            omitted.append(kept[candidate_index].name)
            kept.pop(candidate_index)

        if _total_chars(kept) > self.max_chars:
            kept = _truncate_nonprotected_to_fit(kept, self.max_chars)

        return PromptAssembly(blocks=tuple(kept), omitted_block_names=tuple(omitted), max_chars=self.max_chars)


def _total_chars(blocks: list[PromptBlock]) -> int:
    if not blocks:
        return 0
    return sum(len(block.content) for block in blocks) + max(0, len(blocks) - 1)


def _lowest_value_candidate_index(blocks: list[PromptBlock]) -> int | None:
    candidates = [(index, block) for index, block in enumerate(blocks) if not block.protected]
    if not candidates:
        return None

    def sort_key(item: tuple[int, PromptBlock]) -> tuple[int, int, int]:
        index, block = item
        try:
            order = LOW_PRIORITY_TRUNCATION_ORDER.index(block.name)
        except ValueError:
            order = len(LOW_PRIORITY_TRUNCATION_ORDER)
        return (order, block.priority, index)

    return min(candidates, key=sort_key)[0]


def _truncate_nonprotected_to_fit(blocks: list[PromptBlock], max_chars: int) -> list[PromptBlock]:
    protected_total = _total_chars([block for block in blocks if block.protected])
    available_for_unprotected = max(0, max_chars - protected_total)
    if available_for_unprotected == 0:
        return [block for block in blocks if block.protected]

    truncated: list[PromptBlock] = []
    remaining = available_for_unprotected
    for block in blocks:
        if block.protected:
            truncated.append(block)
            continue
        if remaining <= 0:
            continue
        content = block.content
        if len(content) > remaining:
            marker = TRUNCATION_MARKER if remaining > len(TRUNCATION_MARKER) else ""
            content = content[: max(0, remaining - len(marker))] + marker
        truncated.append(PromptBlock(block.name, content, block.priority, block.protected))
        remaining -= len(content)
    return truncated
