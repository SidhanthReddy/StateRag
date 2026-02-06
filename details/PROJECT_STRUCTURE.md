# State RAG Website Builder - Project Structure

## Overview
A production-grade AI website builder with dual-pane interface (preview + code), per-project State RAG isolation, and prompt visualization.

## Tech Stack
- **Frontend**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS
- **State**: React Context + Custom Hooks
- **Backend**: FastAPI (existing Python backend)
- **Communication**: REST API + Server-Sent Events (SSE) for streaming

## Directory Structure

```
state-rag-builder/
├── backend/                          # Existing Python backend
│   ├── api.py
│   ├── orchestrator.py
│   ├── state_rag_manager.py
│   ├── global_rag.py
│   ├── llm_adapter.py
│   ├── validator.py
│   ├── artifact.py
│   ├── schemas.py
│   ├── state_rag_enums.py
│   ├── llm_output_parser.py
│   ├── global_rag_formatter.py
│   ├── file_lock.py
│   ├── requirements.txt              # NEW
│   └── projects/                     # NEW - Per-project State RAG
│       ├── project_123/
│       │   └── state_rag/
│       │       └── artifacts.json
│       └── project_456/
│           └── state_rag/
│               └── artifacts.json
│
├── frontend/                         # NEW - React frontend
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── main.tsx                  # Entry point
│   │   ├── App.tsx                   # Root component
│   │   ├── vite-env.d.ts
│   │   │
│   │   ├── components/               # UI Components
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx       # Project list + navigation
│   │   │   │   ├── Header.tsx        # Top bar with actions
│   │   │   │   └── Layout.tsx        # Main layout wrapper
│   │   │   │
│   │   │   ├── editor/
│   │   │   │   ├── PromptInput.tsx   # User prompt input
│   │   │   │   ├── CodeEditor.tsx    # Code view panel
│   │   │   │   ├── PreviewPane.tsx   # Live preview iframe
│   │   │   │   └── SplitView.tsx     # Preview/Code split
│   │   │   │
│   │   │   ├── project/
│   │   │   │   ├── ProjectCard.tsx   # Project thumbnail
│   │   │   │   ├── ProjectList.tsx   # All projects view
│   │   │   │   └── CreateProject.tsx # New project modal
│   │   │   │
│   │   │   ├── visualization/
│   │   │   │   ├── PromptVisualizer.tsx      # NEW - Main visualizer
│   │   │   │   ├── FileSelectionPanel.tsx    # NEW - File picker
│   │   │   │   ├── PromptBreakdown.tsx       # NEW - Sections shown
│   │   │   │   └── TokenCounter.tsx          # NEW - Token usage
│   │   │   │
│   │   │   └── common/
│   │   │       ├── Button.tsx
│   │   │       ├── Modal.tsx
│   │   │       ├── Tabs.tsx
│   │   │       └── Loading.tsx
│   │   │
│   │   ├── contexts/                 # React Context
│   │   │   ├── ProjectContext.tsx    # Current project state
│   │   │   ├── EditorContext.tsx     # Editor state (code/preview)
│   │   │   └── AuthContext.tsx       # Future: Authentication
│   │   │
│   │   ├── hooks/                    # Custom React hooks
│   │   │   ├── useProject.ts
│   │   │   ├── useStateRAG.ts
│   │   │   ├── usePromptGeneration.ts
│   │   │   └── useWebSocket.ts
│   │   │
│   │   ├── services/                 # API communication
│   │   │   ├── api.ts                # Base API client
│   │   │   ├── projectService.ts     # Project CRUD
│   │   │   ├── stateRagService.ts    # State RAG operations
│   │   │   ├── orchestratorService.ts # LLM generation
│   │   │   └── globalRagService.ts   # Global RAG queries
│   │   │
│   │   ├── types/                    # TypeScript types
│   │   │   ├── project.ts
│   │   │   ├── artifact.ts
│   │   │   ├── prompt.ts
│   │   │   └── api.ts
│   │   │
│   │   ├── utils/                    # Utility functions
│   │   │   ├── codeFormatter.ts
│   │   │   ├── previewBuilder.ts     # Build HTML for preview
│   │   │   └── promptFormatter.ts    # Format prompt sections
│   │   │
│   │   └── styles/
│   │       ├── index.css             # Global styles + Tailwind
│   │       └── themes.css            # Color themes
│   │
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── postcss.config.js
│
└── docker-compose.yml                # Optional: Containerization
```

## Key Features Implementation

### 1. **Dual-Pane Interface (Lovable-style)**
- **Left Pane**: Live preview in iframe (sandboxed)
- **Right Pane**: Code editor with syntax highlighting
- **Toggle**: Switch between preview-only, code-only, or split view
- **Responsive**: Collapsible panes on mobile

### 2. **Per-Project State RAG Isolation**
- Each project gets unique ID (UUID)
- State RAG stored in `backend/projects/{project_id}/state_rag/`
- StateRAGManager modified to accept `project_id` parameter
- No cross-project contamination

### 3. **Prompt Visualization** (UNIQUE FEATURE)
```
┌─────────────────────────────────────────┐
│ PROMPT BREAKDOWN                        │
├─────────────────────────────────────────┤
│ ✓ System Instructions        (120 tokens) │
│ ✓ Project State (AUTHORITATIVE)          │
│   ├─ components/Navbar.tsx   (450 tokens) │
│   └─ components/Hero.tsx     (320 tokens) │
│ ✓ Global References (ADVISORY)           │
│   ├─ navbar_pattern          (80 tokens)  │
│   └─ hero_pattern            (95 tokens)  │
│ ✓ User Request               (45 tokens)  │
│ ✓ Output Format              (30 tokens)  │
├─────────────────────────────────────────┤
│ TOTAL: 1,140 tokens (~$0.001)           │
└─────────────────────────────────────────┘
```

### 4. **File Selection UI**
- Checkbox list of all active artifacts
- Visual indicator: 🔒 user_modified, 🤖 ai_generated, ✏️ ai_modified
- Real-time token counter as user selects files
- "Select All" / "Select None" / "Select Modified Only"

## Installation & Setup

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn api:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev  # Runs on http://localhost:5173
```

## Development Workflow

1. **User creates new project** → Backend creates isolated State RAG
2. **User types prompt** → Frontend shows file selection panel
3. **User selects files** → Real-time prompt visualization updates
4. **User clicks "Generate"** → API call to orchestrator
5. **Backend streams response** → Frontend updates preview in real-time
6. **User sees result** → Split view: preview (left) + code (right)
7. **User clicks "View Prompt"** → Modal shows exact prompt sent to LLM

## Next Steps
1. Create frontend scaffold (Vite + React + TypeScript)
2. Modify backend API for project isolation
3. Build core UI components
4. Implement prompt visualization
5. Connect frontend ↔ backend
6. Add streaming support
7. Polish UX/UI
