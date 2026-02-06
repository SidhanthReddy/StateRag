from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
import uuid
import os.path

from state_rag_enums import ArtifactType, ArtifactSource


class Artifact(BaseModel):
    # Identity
    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ArtifactType
    name: str
    file_path: str

    # Payload
    content: str
    language: str  # tsx, ts, js, css, json

    # State
    version: int = 1
    is_active: bool = True
    source: ArtifactSource

    # Semantics
    dependencies: List[str] = []  # artifact_ids

    # Metadata
    framework: Optional[str] = "react"
    styling: Optional[str] = "tailwind"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # ------------------
    # Validators (Pydantic v2)
    # ------------------

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Artifact content cannot be empty")
        return v

    @field_validator("file_path")
    @classmethod
    def file_path_must_look_valid(cls, v):
        """
        FIXED VERSION: Secure path validation with traversal protection
        
        Security improvements:
        1. Normalizes paths (resolves .., //, etc.)
        2. Blocks directory traversal attacks (../../../etc/passwd)
        3. Blocks absolute paths (/etc/passwd, C:\Windows\...)
        4. Blocks system directories (etc/, sys/, root/, proc/, dev/)
        
        Valid paths:
        - components/Button.tsx (nested directory)
        - package.json (root file)
        - ./package.json (explicit root)
        - src/index.ts (nested)
        
        Invalid paths (BLOCKED):
        - ../../../etc/passwd (directory traversal - SECURITY)
        - /etc/passwd (absolute system path - SECURITY)
        - C:\Windows\system32 (Windows system - SECURITY)
        - ../../outside/project (escape project root - SECURITY)
        - etc/shadow (system directory - SECURITY)
        """
        
        # Normalize path (resolves .., //, ./, etc.)
        normalized = os.path.normpath(v)
        
        # FIX #1: Block directory traversal
        # Examples: ../../../etc/passwd, ../../outside/project
        if normalized.startswith('..'):
            raise ValueError(f"Directory traversal not allowed: {v}")
        
        # FIX #2: Block absolute paths (Unix and Windows)
        # Examples: /etc/passwd, C:\Windows\system32, D:\data
        if os.path.isabs(normalized):
            raise ValueError(f"Absolute paths not allowed: {v}")
        
        # FIX #3: Block system directories (defense in depth)
        # Even if somehow a path like "etc/passwd" gets through, block it
        forbidden_prefixes = [
            'etc/', 'sys/', 'root/', 'proc/', 'dev/',  # Unix
            'windows/', 'system32/', 'program files/'  # Windows (normalized to lowercase)
        ]
        normalized_lower = normalized.lower().replace('\\', '/')
        if any(normalized_lower.startswith(prefix) for prefix in forbidden_prefixes):
            raise ValueError(f"System paths not allowed: {v}")
        
        # FIX #4: Block paths starting with root separator
        # Examples: \etc\passwd (Windows style), /usr/bin
        if normalized.startswith(('/', '\\')):
            raise ValueError(f"Paths cannot start with separator: {v}")
        
        # Return normalized version (converts backslashes to forward slashes on Windows)
        return normalized.replace('\\', '/')

    @field_validator("language")
    @classmethod
    def language_must_be_known(cls, v):
        allowed = {"tsx", "ts", "js", "css", "json", "jsx"}  # Added jsx
        if v not in allowed:
            raise ValueError(f"Unsupported language: {v}")
        return v