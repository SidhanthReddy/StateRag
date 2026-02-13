import streamlit as st
from api_client import APIClient

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
            st.session_state.generated_files = []  # Reset on project change

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

artifacts = project.get("artifacts", [])

st.title(project["name"])

# -----------------------------
# File Selection Panel
# -----------------------------
st.subheader("Project Files (Authoritative State)")

selected_files = []

for a in artifacts:
    icon = "🤖"
    if a["source"] == "user_modified":
        icon = "🔒"
    elif a["source"] == "ai_modified":
        icon = "✏️"

    checked = st.checkbox(
        f"{icon} {a['file_path']}",
        value=True,
        key=a["artifact_id"]
    )

    if checked:
        selected_files.append(a["file_path"])

st.session_state.selected_files = selected_files

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
# Prompt Preview
# -----------------------------
if col1.button("Preview Prompt"):
    if user_prompt:
        preview = api.preview_prompt(
            st.session_state.selected_project,
            user_prompt,
            st.session_state.selected_files or ["*"]
        )

        st.session_state.last_prompt_files = preview.get("selected_files", [])

        st.subheader("Prompt Breakdown")
        st.write(f"Total Tokens: {preview['total_tokens']}")
        st.write(f"Estimated Cost: ${preview['estimated_cost']}")

        st.subheader("State RAG Context")

        if st.session_state.last_prompt_files:
            st.success("Selective Retrieval Active")
            st.write("Files injected into prompt:")
            for f in st.session_state.last_prompt_files:
                st.write(f"• {f}")
        else:
            st.info("No project files were needed for this request.")

        for section in preview["sections"]:
            with st.expander(section["title"]):
                st.write(f"Tokens: {section['tokens']}")
                st.code(section["content"])

# -----------------------------
# Generate
# -----------------------------
if col2.button("Generate"):
    if user_prompt:
        with st.spinner("Generating..."):
            try:
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

                # Persist modified files
                st.session_state.generated_files = result["artifacts"]

                # Reload project state after commit
                project = api.get_project(st.session_state.selected_project)
                artifacts = project.get("artifacts", [])

            except Exception as e:
                st.error(str(e))

# -----------------------------
# Show Generated / Modified Files
# -----------------------------
if st.session_state.generated_files:

    st.subheader("Modified / Generated Files")

    for artifact in st.session_state.generated_files:
        with st.expander(f"🆕 {artifact['file_path']}", expanded=True):
            st.code(artifact["content"], language="javascript")
