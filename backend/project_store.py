import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from file_lock import FileLock


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
PROJECTS_FILE = os.path.join(PROJECTS_DIR, "projects.json")


def _ensure_projects_file() -> None:
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    if not os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, "w") as f:
            json.dump([], f, indent=2)


def _load_projects() -> List[Dict]:
    _ensure_projects_file()
    with FileLock(PROJECTS_FILE):
        with open(PROJECTS_FILE, "r") as f:
            return json.load(f)


def _save_projects(projects: List[Dict]) -> None:
    _ensure_projects_file()
    with FileLock(PROJECTS_FILE):
        with open(PROJECTS_FILE, "w") as f:
            json.dump(projects, f, indent=2)


def list_projects() -> List[Dict]:
    return _load_projects()


def get_project(project_id: str) -> Optional[Dict]:
    projects = _load_projects()
    return next((p for p in projects if p["project_id"] == project_id), None)


def create_project(project_id: str, name: str, template: Optional[str] = None) -> Dict:
    now = datetime.utcnow().isoformat()
    project = {
        "project_id": project_id,
        "name": name,
        "template": template,
        "created_at": now,
        "updated_at": now,
    }

    projects = _load_projects()
    projects.append(project)
    _save_projects(projects)
    return project


def update_project_timestamp(project_id: str) -> None:
    projects = _load_projects()
    now = datetime.utcnow().isoformat()
    for project in projects:
        if project["project_id"] == project_id:
            project["updated_at"] = now
            break
    _save_projects(projects)


def delete_project(project_id: str) -> bool:
    projects = _load_projects()
    remaining = [p for p in projects if p["project_id"] != project_id]
    if len(remaining) == len(projects):
        return False
    _save_projects(remaining)
    return True
