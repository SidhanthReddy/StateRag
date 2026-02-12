import os
import shutil
import time
import uuid
from typing import List, Optional
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from artifact import Artifact
from global_rag import GlobalRAG
from orchestrator import Orchestrator
from project_store import (
    PROJECTS_DIR,
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project_timestamp,
)
from state_rag_manager import StateRAGManager


app = FastAPI()


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    template: Optional[str] = None


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    template: Optional[str] = None
    created_at: str
    updated_at: str


class GenerateRequest(BaseModel):
    project_id: str
    user_request: str
    allowed_paths: Optional[List[str]] = None


class PromptSection(BaseModel):
    title: str
    content: str
    tokens: int


class PromptPreviewResponse(BaseModel):
    sections: List[PromptSection]
    total_tokens: int
    estimated_cost: float
    selected_files: List[str]


def _init_project_storage(project_id: str) -> None:
    state_dir = os.path.join(PROJECTS_DIR, project_id, "state_rag")
    os.makedirs(state_dir, exist_ok=True)
    artifacts_path = os.path.join(state_dir, "artifacts.json")
    if not os.path.exists(artifacts_path):
        with open(artifacts_path, "w") as f:
            f.write("[]")


def _token_count(text: str) -> int:
    return max(1, len(text) // 4)


def _estimate_cost(token_count: int, cost_per_1k: float = 0.001) -> float:
    return round((token_count / 1000) * cost_per_1k, 6)


def _build_prompt_sections(
    user_request: str,
    active_artifacts: List[Artifact],
    global_refs,
    allowed_paths: List[str],
) -> List[PromptSection]:
    sections: List[PromptSection] = []

    system_text = (
        "You are an AI website builder.\n"
        "You are stateless.\n"
        "PROJECT STATE is authoritative.\n"
        "GLOBAL REFERENCES are advisory.\n"
        "Modify only explicitly allowed files.\n"
        "Output full updated files only.\n"
    )
    sections.append(
        PromptSection(
            title="System Instructions",
            content=system_text,
            tokens=_token_count(system_text),
        )
    )

    project_lines = []
    for artifact in active_artifacts:
        project_lines.append(f"--- {artifact.file_path} ---")
        project_lines.append(artifact.content)
    project_text = "\n".join(project_lines) if project_lines else "(No project artifacts selected.)"
    sections.append(
        PromptSection(
            title="Project State (Authoritative)",
            content=project_text,
            tokens=_token_count(project_text),
        )
    )

    global_lines = []
    for idx, ref in enumerate(global_refs, 1):
        global_lines.append(f"{idx}. {ref.title}")
        global_lines.append(ref.content)
    global_text = "\n".join(global_lines) if global_lines else "(No global references retrieved.)"
    sections.append(
        PromptSection(
            title="Global References (Advisory)",
            content=global_text,
            tokens=_token_count(global_text),
        )
    )

    allowed_text = "\n".join(f"- {path}" for path in allowed_paths)
    sections.append(
        PromptSection(
            title="Allowed Files",
            content=allowed_text,
            tokens=_token_count(allowed_text),
        )
    )

    sections.append(
        PromptSection(
            title="User Request",
            content=user_request,
            tokens=_token_count(user_request),
        )
    )

    output_text = "FILE: <file_path>\n<full file content>\n"
    sections.append(
        PromptSection(
            title="Output Format",
            content=output_text,
            tokens=_token_count(output_text),
        )
    )

    return sections


def _build_prompt_text(sections: List[PromptSection]) -> str:
    text_sections = []
    for section in sections:
        text_sections.append(f"{section.title}:\n{section.content}")
    return "\n\n".join(text_sections)


@app.get("/api/projects", response_model=List[ProjectResponse])
def list_projects_endpoint():
    return list_projects()


@app.post("/api/projects", response_model=ProjectResponse)
def create_project_endpoint(req: ProjectCreateRequest):
    project_id = str(uuid.uuid4())
    project = create_project(project_id=project_id, name=req.name, template=req.template)
    _init_project_storage(project_id)
    return project


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def get_project_endpoint(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.delete("/api/projects/{project_id}")
def delete_project_endpoint(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    removed = delete_project(project_id)
    if not removed:
        raise HTTPException(status_code=500, detail="Failed to delete project")

    project_dir = os.path.join(PROJECTS_DIR, project_id)
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir)
    return {"status": "ok"}


@app.post("/api/prompt/preview", response_model=PromptPreviewResponse)
def preview_prompt(req: GenerateRequest):
    if not get_project(req.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    allowed_paths = req.allowed_paths or ["*"]
    file_paths = None if "*" in allowed_paths else req.allowed_paths
    state_rag = StateRAGManager(project_id=req.project_id)
    active_artifacts = state_rag.retrieve(
        file_paths=file_paths,
        user_query=req.user_request
    )

    global_rag = GlobalRAG()
    global_refs = global_rag.retrieve(query=req.user_request, k=3)

    sections = _build_prompt_sections(
        user_request=req.user_request,
        active_artifacts=active_artifacts,
        global_refs=global_refs,
        allowed_paths=allowed_paths,
    )

    total_tokens = sum(section.tokens for section in sections)
    return PromptPreviewResponse(
        sections=sections,
        total_tokens=total_tokens,
        estimated_cost=_estimate_cost(total_tokens),
        selected_files=[artifact.file_path for artifact in active_artifacts],
    )


@app.post("/api/prompt/text")
def prompt_text(req: GenerateRequest):
    if not get_project(req.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    allowed_paths = req.allowed_paths or ["*"]
    file_paths = None if "*" in allowed_paths else req.allowed_paths
    state_rag = StateRAGManager(project_id=req.project_id)
    active_artifacts = state_rag.retrieve(file_paths=file_paths)
    global_rag = GlobalRAG()
    global_refs = global_rag.retrieve(query=req.user_request, k=3)

    sections = _build_prompt_sections(
        user_request=req.user_request,
        active_artifacts=active_artifacts,
        global_refs=global_refs,
        allowed_paths=allowed_paths,
    )
    return {"prompt": _build_prompt_text(sections)}


@app.post("/api/generate")
def generate_code(req: GenerateRequest):
    if not get_project(req.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    allowed_paths = req.allowed_paths or ["*"]
    llm_provider = os.getenv("LLM_PROVIDER", "mock")
    print("Using LLM Provider:", llm_provider)

    state_rag = StateRAGManager(project_id=req.project_id)
    global_rag = GlobalRAG()
    orchestrator = Orchestrator(
        llm_provider=llm_provider,
        project_id=req.project_id,
        state_rag=state_rag,
        global_rag=global_rag,
    )

    start = time.time()
    artifacts = orchestrator.handle_request(
        user_request=req.user_request,
        allowed_paths=allowed_paths,
    )
    duration = time.time() - start
    update_project_timestamp(req.project_id)

    return {
        "artifacts": [artifact.dict() for artifact in artifacts],
        "llm_provider": llm_provider,
        "generation_time": round(duration, 3),
    }
