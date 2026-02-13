import re
from typing import List

from validator import ProposedArtifact


class LLMOutputParseError(Exception):
    """Raised when LLM output is malformed or ambiguous."""


FILE_HEADER_REGEX = re.compile(r"^FILE:\s*(.+)$", re.MULTILINE)


def parse_llm_output(raw: str) -> List[ProposedArtifact]:
    """
    Parses raw LLM output into ProposedArtifact objects.

    Expected format:

    FILE: path/to/file.tsx
    <full file content>

    FILE: another/file.ts
    <full file content>
    """

    if not raw or not raw.strip():
        raise LLMOutputParseError("LLM output is empty")

    matches = list(FILE_HEADER_REGEX.finditer(raw))

    if not matches:
        raise LLMOutputParseError("No FILE headers found in LLM output")

    artifacts: List[ProposedArtifact] = []
    for i, match in enumerate(matches):
        file_path = match.group(1).strip()

        # Normalize JSX → TSX
        if file_path.endswith(".jsx"):
            file_path = file_path[:-4] + ".tsx"
        
        if not file_path:
            raise LLMOutputParseError("Empty file path in FILE header")

        content_start = match.end()

        if i + 1 < len(matches):
            content_end = matches[i + 1].start()
        else:
            content_end = len(raw)

        content = raw[content_start:content_end].strip()

        if not content:
            raise LLMOutputParseError(
                f"Empty content for file: {file_path}"
            )

        language = _infer_language(file_path)

        artifacts.append(
            ProposedArtifact(
                file_path=file_path,
                content=content,
                language=language,
            )
        )

    return artifacts


def _infer_language(file_path: str) -> str:
    file_path = file_path.lower()

    if file_path.endswith(".tsx"):
        return "tsx"
    if file_path.endswith(".ts"):
        return "ts"
    if file_path.endswith(".jsx"):
        return "js"
    if file_path.endswith(".js"):
        return "js"
    if file_path.endswith(".css"):
        return "css"
    if file_path.endswith(".json"):
        return "json"
    if file_path.endswith(".html"):
        return "html"

    return "tsx"

