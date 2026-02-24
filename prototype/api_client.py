import requests
import os

BASE_URL = os.getenv("STATE_RAG_API_BASE_URL", "http://127.0.0.1:8000/api")


class APIClient:
    def list_projects(self):
        try:
            response = requests.get(f"{BASE_URL}/projects", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def ui_mutate(self, project_id, file_path, mutation):
        return requests.post(
            f"{BASE_URL}/ui/mutate",
            json={
                "project_id": project_id,
                "file_path": file_path,
                "mutation": mutation
            }
        ).json()

    def create_project(self, name):
        return requests.post(
            f"{BASE_URL}/projects",
            json={"name": name}
        ).json()

    def delete_project(self, project_id):
        return requests.delete(
            f"{BASE_URL}/projects/{project_id}"
        ).json()

    def get_project(self, project_id):
        return requests.get(
            f"{BASE_URL}/projects/{project_id}"
        ).json()

    def preview_prompt(self, project_id, user_request, allowed_paths):
        return requests.post(
            f"{BASE_URL}/prompt/preview",
            json={
                "project_id": project_id,
                "user_request": user_request,
                "allowed_paths": allowed_paths
            }
        ).json()

    def generate(self, project_id, user_request, allowed_paths):
        return requests.post(
            f"{BASE_URL}/generate",
            json={
                "project_id": project_id,
                "user_request": user_request,
                "allowed_paths": allowed_paths
            }
            ).json()
        
    def get_artifacts(self, project_id):
        return requests.get(f"{BASE_URL}/projects/{project_id}/artifacts").json()

