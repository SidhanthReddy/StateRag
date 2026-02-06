from typing import List
from schemas import GlobalRAGEntry

MAX_ENTRY_CHARS = 300
MAX_TOTAL_CHARS = 1200


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def format_global_rag_for_prompt(
    entries: List[GlobalRAGEntry],
) -> str:
    """
    Formats Global RAG entries into prompt-safe advisory text.
    This output is non-authoritative and bounded.
    """

    if not entries:
        return ""

    lines = []
    total_chars = 0
    count = 1

    for entry in entries:
        title = _truncate(entry.title, 80)
        content = _truncate(entry.content, MAX_ENTRY_CHARS)

        block = (
            f"{count}. {title}\n"
            f"   {content}"
        )

        if total_chars + len(block) > MAX_TOTAL_CHARS:
            break

        lines.append(block)
        total_chars += len(block)
        count += 1

    header = "GLOBAL REFERENCES (advisory):\n"
    return header + "\n\n".join(lines)
