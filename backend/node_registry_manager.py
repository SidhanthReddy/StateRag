import os
import json
from typing import Dict

from project_store import PROJECTS_DIR
from file_lock import FileLock, SharedFileLock


class NodeRegistryManager:

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.registry_path = os.path.join(
            PROJECTS_DIR,
            project_id,
            "node_registry.json"
        )

        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        if not os.path.exists(self.registry_path):
            self._initialize_registry()

        self.registry = self._load()

    def _initialize_registry(self):
        with FileLock(self.registry_path):
            with open(self.registry_path, "w") as f:
                json.dump({}, f, indent=2)

    def _load(self) -> Dict:
        with SharedFileLock(self.registry_path):
            with open(self.registry_path, "r") as f:
                return json.load(f)

    def _save(self):
        with FileLock(self.registry_path):
            with open(self.registry_path, "w") as f:
                json.dump(self.registry, f, indent=2)

    def ensure_file_entry(self, file_path: str):
        if file_path not in self.registry:
            self.registry[file_path] = {}

    def register_node(self, file_path: str, node_id: str, element_type: str):
        self.ensure_file_entry(file_path)

        if node_id not in self.registry[file_path]:
            self.registry[file_path][node_id] = {
                "element_type": element_type,
                "user_modified": False,
                "locked_groups": [],
                "locked_classes": [],
                "layout": {
                    "width": None,
                    "height": None,
                    "position": None,
                    "x": None,
                    "y": None
                },
                "meta": {}
            }

        self._save()

    def lock_group(self, file_path: str, node_id: str, group: str):
        self.ensure_file_entry(file_path)

        node = self.registry[file_path].get(node_id)
        if not node:
            return

        if group not in node["locked_groups"]:
            node["locked_groups"].append(group)

        node["user_modified"] = True
        self._save()
