from typing import List, Tuple

from artifact import Artifact


REACT_ENTRY_CANDIDATES = {
    "app.tsx",
    "app.jsx",
    "main.tsx",
    "main.jsx",
    "index.tsx",
    "index.jsx",
}


def validate_runtime(artifacts: List[Artifact]) -> Tuple[bool, List[str]]:
    """
    Lightweight runtime validation to ensure a preview can be built.

    This does not execute code. It checks for entrypoints and basic structure
    so the frontend can render a preview reliably.
    """
    errors: List[str] = []

    if not artifacts:
        return False, ["No artifacts available for runtime validation."]

    file_paths = [artifact.file_path.lower() for artifact in artifacts]
    has_html = any(path.endswith(".html") for path in file_paths)
    has_react = any(
        path.endswith((".tsx", ".jsx", ".ts", ".js"))
        for path in file_paths
    )

    if has_html:
        html_files = [
            artifact
            for artifact in artifacts
            if artifact.file_path.lower().endswith(".html")
        ]
        if not any("<html" in artifact.content.lower() for artifact in html_files):
            errors.append("HTML output missing <html> tag.")
        if not any("<body" in artifact.content.lower() for artifact in html_files):
            errors.append("HTML output missing <body> tag.")

    if has_react:
        entry_matches = [
            artifact
            for artifact in artifacts
            if artifact.file_path.lower().endswith(tuple(REACT_ENTRY_CANDIDATES))
        ]
        if not entry_matches:
            errors.append(
                "React output missing entrypoint (expected App.tsx or main.tsx)."
            )
        else:
            entry_content = "\n".join(a.content for a in entry_matches).lower()
            if "export default" not in entry_content and "createroot" not in entry_content:
                errors.append("React entrypoint missing export default or createRoot call.")

    if not has_html and not has_react:
        errors.append("No HTML or React entrypoints found in artifacts.")

    return len(errors) == 0, errors
