from dataclasses import dataclass
from typing import List, Dict, Optional

from artifact import Artifact
from state_rag_enums import ArtifactSource


# =========================
# Data contracts
# =========================

@dataclass
class ProposedArtifact:
    file_path: str
    content: str
    language: str


@dataclass
class ValidationResult:
    ok: bool
    artifacts: Optional[List[ProposedArtifact]] = None
    reason: Optional[str] = None


# =========================
# Validator rules
# =========================

class ValidationRule:
    def check(
        self,
        proposed: List[ProposedArtifact],
        active: Dict[str, Artifact],
        allowed_paths: List[str],
    ) -> ValidationResult:
        raise NotImplementedError
def _is_allowed(file_path: str, allowed_paths: List[str]) -> bool:
    return "*" in allowed_paths or file_path in allowed_paths

# -------------------------
# 1. Syntax Validator
# -------------------------

class SyntaxValidator(ValidationRule):
    def check(self, proposed, active, allowed_paths):
        for p in proposed:
            if not p.content or not p.content.strip():
                return ValidationResult(
                    ok=False,
                    reason=f"Empty content for {p.file_path}"
                )

            if not p.file_path.endswith(self._ext_for_lang(p.language)):
                return ValidationResult(
                    ok=False,
                    reason=f"Language/file mismatch for {p.file_path}"
                )

        return ValidationResult(ok=True)

    def _ext_for_lang(self, lang: str) -> str:
        return {
            "tsx": ".tsx",
            "ts": ".ts",
            "js": ".js",
            "json": ".json",
        }.get(lang, "")


# -------------------------
# 2. Authority Validator (FIXED)
# -------------------------

class AuthorityValidator(ValidationRule):
    """
    FIXED VERSION:
    - User-modified files CAN be modified if they're in allowed_paths
    - Only block if user file is NOT in allowed_paths (user didn't give permission)
    """
    def check(self, proposed, active, allowed_paths):
        for p in proposed:
            if p.file_path in active:
                old = active[p.file_path]

                # BUG WAS HERE: Logic was inverted!
                # OLD (WRONG): if user_modified AND not in allowed_paths -> block
                # NEW (CORRECT): if user_modified AND in allowed_paths -> ALLOW
                #                if user_modified AND not in allowed_paths -> BLOCK
                
                if old.source == ArtifactSource.user_modified:
                    if not _is_allowed(p.file_path, allowed_paths):
                        # User file but NOT in allowed list = unauthorized
                        return ValidationResult(
                            ok=False,
                            reason=(
                                f"Unauthorized modification of user file: "
                                f"{p.file_path}. User must explicitly allow this file."
                            )
                        )
                    # else: User file IS in allowed_paths = OK! Continue.

        return ValidationResult(ok=True)


# -------------------------
# 3. Scope Validator
# -------------------------

class ScopeValidator(ValidationRule):
    def check(self, proposed, active, allowed_paths):
        for p in proposed:
            if not _is_allowed(p.file_path, allowed_paths):
                return ValidationResult(
                    ok=False,
                    reason=f"Out-of-scope modification: {p.file_path}"
                )
        return ValidationResult(ok=True)


# -------------------------
# 4. Consistency Validator
# -------------------------

class ConsistencyValidator(ValidationRule):
    def check(self, proposed, active, allowed_paths):
        seen = set()
        for p in proposed:
            if p.file_path in seen:
                return ValidationResult(
                    ok=False,
                    reason=f"Duplicate artifact for {p.file_path}"
                )
            seen.add(p.file_path)

        return ValidationResult(ok=True)


# =========================
# Validator Orchestrator
# =========================

class Validator:
    def __init__(self):
        self.rules: List[ValidationRule] = [
            SyntaxValidator(),
            AuthorityValidator(),
            ScopeValidator(),
            ConsistencyValidator(),
        ]

    def validate(
        self,
        proposed: List[ProposedArtifact],
        active_artifacts: List[Artifact],
        allowed_paths: List[str],
    ) -> ValidationResult:

        active_lookup = {
            a.file_path: a
            for a in active_artifacts
            if a.is_active
        }

        for rule in self.rules:
            result = rule.check(
                proposed=proposed,
                active=active_lookup,
                allowed_paths=allowed_paths,
            )
            if not result.ok:
                return result

        return ValidationResult(ok=True, artifacts=proposed)