import streamlit as st
from api_client import APIClient
import re

api = APIClient()
st.set_page_config(layout="wide")

# -----------------------------
# Session State
# -----------------------------
if "selected_project" not in st.session_state:
    st.session_state.selected_project = None

if "selected_files" not in st.session_state:
    st.session_state.selected_files = []

if "generated_files" not in st.session_state:
    st.session_state.generated_files = []

if "last_prompt_files" not in st.session_state:
    st.session_state.last_prompt_files = []

# -----------------------------
# Sidebar - Projects
# -----------------------------
st.sidebar.title("Projects")

projects = api.list_projects()

if isinstance(projects, dict) and "error" in projects:
    st.sidebar.error("Backend not reachable.")
    st.stop()

elif not isinstance(projects, list):
    st.sidebar.error("Unexpected response from backend.")
    st.stop()

else:
    for p in projects:
        if st.sidebar.button(p["name"], key=p["project_id"]):
            st.session_state.selected_project = p["project_id"]
            st.session_state.generated_files = []
            st.rerun()

st.sidebar.divider()

new_project_name = st.sidebar.text_input("New Project Name")

if st.sidebar.button("Create Project"):
    if new_project_name:
        api.create_project(new_project_name)
        st.rerun()

# -----------------------------
# Main Panel
# -----------------------------
if not st.session_state.selected_project:
    st.title("State RAG Builder Prototype")
    st.write("Select or create a project from the sidebar.")
    st.stop()

project = api.get_project(st.session_state.selected_project)

if isinstance(project, dict) and "error" in project:
    st.error("Failed to fetch project.")
    st.stop()

st.title(project["name"])

# 🔥 IMPORTANT FIX:
# Always fetch artifacts explicitly
artifacts_response = api.get_artifacts(st.session_state.selected_project)
artifacts = artifacts_response.get("artifacts", [])

# -----------------------------
# File Viewer
# -----------------------------
st.divider()
st.subheader("File Viewer")

file_paths = [a["file_path"] for a in artifacts]

if not file_paths:
    st.warning("No files available yet.")
    selected_file_path = None
else:
    selected_file_path = st.selectbox(
        "Select a file to inspect / mutate",
        file_paths
    )

selected_file_content = None
selected_artifact = None

if selected_file_path:
    for a in artifacts:
        if a["file_path"] == selected_file_path:
            selected_file_content = a["content"]
            selected_artifact = a
            break

if selected_file_content:
    st.code(selected_file_content, language="javascript")

# -----------------------------
# File Selection (State RAG)
# -----------------------------
if False:
    # ----------------------------- # File Selection (State RAG) # ----------------------------- 
    st.subheader("Project Files (Authoritative State)")
    selected_files = []
    for a in artifacts:
        icon = "🤖"
        if a["source"] == "user_modified":
            icon = "🔒"
        elif a["source"] == "ai_modified":
            icon = "✏️"
        elif a["source"] == "system_generated":
            icon = "⚙️"
        checked = st.checkbox(
            f"{icon} {a['file_path']}",
            value=True,
            key=f"chk_{a['artifact_id']}"
        )
        if checked:
            selected_files.append(a["file_path"])
    st.session_state.selected_files = selected_files
# -----------------------------
# Node ID Detection
# -----------------------------
first_node_id = None

if selected_file_content:
    match = re.search(r'data-node-id="([^"]+)"', selected_file_content)
    if match:
        first_node_id = match.group(1)
        st.info(f"Detected first node-id: {first_node_id}")
    else:
        st.warning("No data-node-id detected yet.")

# -----------------------------
# Inject IDs
# -----------------------------
if selected_file_path:
    if st.button("Inject Node IDs"):
        api.ui_mutate(
            st.session_state.selected_project,
            selected_file_path,
            {"type": "noop"}
        )
        st.rerun()

# -----------------------------
# Apply UI Mutation
# -----------------------------
if first_node_id and selected_file_path:
    if st.button("Apply UI Mutation (Add bg-yellow-500)"):
        response = api.ui_mutate(
            st.session_state.selected_project,
            selected_file_path,
            {
                "type": "update_classname",
                "nodeId": first_node_id,
                "add": ["bg-yellow-500"],
                "remove": []
            }
        )

        if "error" in response:
            st.error(response["error"])
        else:
            st.success("UI Mutation Applied")
            st.rerun()

# -----------------------------
# Prompt Input
# -----------------------------
st.subheader("Prompt")

user_prompt = st.text_area(
    "Enter your request",
    height=120
)

col1, col2 = st.columns(2)

# -----------------------------
# Preview Prompt
# -----------------------------
if col1.button("Preview Prompt"):
    if user_prompt:
        preview = api.preview_prompt(
            st.session_state.selected_project,
            user_prompt,
            st.session_state.selected_files or ["*"]
        )

        st.session_state.last_prompt_files = preview.get("selected_files", [])

        st.subheader("State RAG Context")

        if st.session_state.last_prompt_files:
            st.success("Selective Retrieval Active")
            for f in st.session_state.last_prompt_files:
                st.write(f"• {f}")
        else:
            st.info("No project files were needed for this request.")

# -----------------------------
# Generate
# -----------------------------
if col2.button("Generate"):
    if user_prompt:
        with st.spinner("Generating..."):
            result = api.generate(
                st.session_state.selected_project,
                user_prompt,
                st.session_state.selected_files or ["*"]
            )

            if result.get("injected_files"):
                st.subheader("Files Injected Into This Generation")
                for f in result["injected_files"]:
                    st.write(f"- {f}")

            st.success("Generation Complete")
            st.session_state.generated_files = result["artifacts"]
            st.rerun()

# -----------------------------
# Show Modified / Generated Files
# -----------------------------
if st.session_state.generated_files:
    st.subheader("Modified / Generated Files")

    for artifact in st.session_state.generated_files:
        with st.expander(f"🆕 {artifact['file_path']}", expanded=True):
            st.code(artifact["content"], language="javascript")
