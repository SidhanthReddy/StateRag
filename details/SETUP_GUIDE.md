# 🚀 State RAG Builder - Setup & Deployment Guide

## 📁 File Structure

```
state-rag-builder/
├── backend/                          # Python FastAPI backend
│   ├── api_v2.py                    # NEW - Enhanced API with project support
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
│   ├── global_rag.json              # Global knowledge base
│   ├── global_rag.index             # FAISS index
│   ├── requirements.txt
│   └── projects/                     # Per-project State RAG
│       ├── projects.json             # Project registry
│       └── {project_id}/
│           └── state_rag/
│               └── artifacts.json
│
└── frontend/                         # React + TypeScript frontend
    ├── public/
    │   └── index.html
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── components/
    │   │   ├── layout/
    │   │   ├── editor/
    │   │   │   ├── SplitView.tsx
    │   │   │   ├── PreviewPane.tsx
    │   │   │   ├── CodeEditor.tsx
    │   │   │   └── PromptInput.tsx
    │   │   ├── visualization/
    │   │   │   ├── PromptVisualizer.tsx      # ⭐ Signature feature
    │   │   │   └── FileSelectionPanel.tsx    # ⭐ File selection with authority
    │   │   └── common/
    │   ├── pages/
    │   │   ├── HomePage.tsx
    │   │   └── ProjectPage.tsx
    │   ├── services/
    │   │   ├── api.ts
    │   │   ├── projectService.ts
    │   │   └── orchestratorService.ts
    │   ├── types/
    │   │   ├── artifact.ts
    │   │   ├── project.ts
    │   │   └── prompt.ts
    │   └── styles/
    │       └── index.css
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── tailwind.config.js
    └── postcss.config.js
```

---

## 🛠️ Installation & Setup

### Prerequisites
- **Python 3.9+**
- **Node.js 18+** & npm
- **Git**

---

### Step 1: Clone & Setup Backend

```bash
# Navigate to your backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn sentence-transformers faiss-cpu numpy pydantic python-dotenv google-generativeai

# Create requirements.txt
pip freeze > requirements.txt

# Create .env file for API keys
cat > .env << EOF
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here  # Optional
EOF

# Test backend
python api_v2.py
# Should start on http://localhost:8000
```

---

### Step 2: Setup Frontend

```bash
# Navigate to frontend directory
cd ../frontend

# Install dependencies
npm install

# Start development server
npm run dev
# Should start on http://localhost:5173
```

---

## 🚀 Running the Application

### Development Mode

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python api_v2.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Open browser:** http://localhost:5173

---

### Production Build

**Frontend:**
```bash
cd frontend
npm run build
# Output in: frontend/dist/
```

**Backend:**
```bash
cd backend
pip install gunicorn  # Production server
gunicorn api_v2:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 📋 Where to Place Your Existing Files

### Backend Files (Python)
Place your existing files in `backend/` directory:

```
backend/
├── api_v2.py              ← NEW (use this instead of api.py)
├── orchestrator.py        ← Your existing file
├── state_rag_manager.py   ← Your existing file
├── global_rag.py          ← Your existing file
├── llm_adapter.py         ← Your existing file
├── validator.py           ← Your existing file
├── artifact.py            ← Your existing file
├── schemas.py             ← Your existing file
├── state_rag_enums.py     ← Your existing file
├── llm_output_parser.py   ← Your existing file
├── global_rag_formatter.py ← Your existing file
├── file_lock.py           ← Your existing file
├── global_rag.json        ← Your existing file
└── global_rag.index       ← Your existing file (if exists)
```

### Frontend Files (React)
All frontend files go in `frontend/` directory (see structure above).

---

## 🔑 API Keys Setup

### Gemini API Key (Free Tier)
1. Go to https://makersuite.google.com/app/apikey
2. Create API key
3. Add to `backend/.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```

### OpenAI API Key (Optional)
1. Go to https://platform.openai.com/api-keys
2. Create API key
3. Add to `backend/.env`:
   ```
   OPENAI_API_KEY=your_key_here
   ```

---

## 🎨 Key Features Implemented

### 1. **Dual-Pane Interface** (Lovable-style)
- **Preview Pane**: Live HTML preview with iframe sandboxing
- **Code Pane**: Monaco editor with syntax highlighting
- **Split View**: Adjustable split ratio with drag handle
- **Toggle**: Switch between preview-only, code-only, or split

**File:** `frontend/src/components/editor/SplitView.tsx`

### 2. **Per-Project State RAG Isolation**
- Each project gets unique State RAG instance
- No cross-project contamination
- Isolated storage in `backend/projects/{project_id}/`

**Files:**
- `backend/api_v2.py` - Project management endpoints
- `backend/projects/` - Per-project storage

### 3. **Prompt Visualization** ⭐ (SIGNATURE FEATURE)
- Real-time prompt breakdown
- Token counting per section
- Cost estimation
- File selection panel with authority indicators
- Full prompt text viewer

**Files:**
- `frontend/src/components/visualization/PromptVisualizer.tsx`
- `frontend/src/components/visualization/FileSelectionPanel.tsx`
- `backend/api_v2.py` - `/api/prompt/preview` endpoint

---

## 📊 Prompt Visualization - How It Works

```
User Types Prompt
       ↓
Selects Files (with checkboxes)
       ↓
Clicks "Preview Prompt" or "Generate"
       ↓
Backend builds prompt breakdown:
  ├─ System Instructions
  ├─ Project State (AUTHORITATIVE) - Selected files
  ├─ Global References (ADVISORY) - Retrieved patterns
  ├─ User Request
  └─ Output Format
       ↓
Frontend shows breakdown:
  ├─ Token count per section
  ├─ Estimated cost
  ├─ Expandable sections
  ├─ File contents preview
  └─ "View Full Prompt" button
```

**Backend Endpoint:**
```
POST /api/prompt/preview
{
  "project_id": "uuid",
  "user_request": "Create a navbar",
  "allowed_paths": ["components/Navbar.tsx"]
}

Response:
{
  "sections": [...],
  "total_tokens": 1240,
  "estimated_cost": 0.00124,
  "selected_files": [...]
}
```

---

## 🔐 File Selection with Authority Indicators

**Visual Indicators:**
- 🔒 **Yellow** - `user_modified` (User Protected)
- 🤖 **Blue** - `ai_generated` (AI Generated)
- ✏️ **Purple** - `ai_modified` (AI Modified)

**Features:**
- Search files by name/path
- Group by type or source
- Quick actions: Select All, Clear, Modified Only
- Real-time token counter

**File:** `frontend/src/components/visualization/FileSelectionPanel.tsx`

---

## 🧪 Testing the Application

### 1. Create Your First Project
1. Open http://localhost:5173
2. Click "New Project"
3. Enter name (e.g., "My Landing Page")
4. Select template (e.g., "Landing Page")
5. Click "Create Project"

### 2. Generate Your First Component
1. In the prompt input, type:
   ```
   Create a modern navbar with logo on the left, 
   navigation links in the center, and a CTA button on the right. 
   Use purple gradient for the CTA.
   ```
2. Click "Preview Prompt" to see what will be sent to LLM
3. Review token count and selected files
4. Click "Generate"
5. Watch as the preview and code appear!

### 3. Test Prompt Visualization
1. Click "Preview Prompt" before generating
2. Expand each section to see details
3. Click "View Full Prompt Text"
4. Copy prompt to clipboard if needed

---

## 🐛 Troubleshooting

### Backend Issues

**Port already in use:**
```bash
# Kill process on port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux:
lsof -ti:8000 | xargs kill -9
```

**Import errors:**
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

**FAISS errors:**
```bash
# Install FAISS CPU version
pip install faiss-cpu
```

### Frontend Issues

**Module not found:**
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

**Port 5173 in use:**
```bash
# Change port in vite.config.ts
server: {
  port: 3000,  // Use different port
}
```

---

## 🚀 Next Steps

### Recommended Enhancements

1. **Authentication**
   - Add user login/signup
   - Protect projects per user

2. **Real-time Collaboration**
   - WebSocket support
   - Live cursor positions
   - Collaborative editing

3. **Export/Deploy**
   - Export to ZIP
   - Deploy to Vercel/Netlify
   - GitHub integration

4. **Enhanced Preview**
   - Mobile device emulation
   - Different screen sizes
   - Dark mode toggle

5. **AI Improvements**
   - Streaming responses
   - Multiple LLM providers
   - Custom system prompts

6. **Analytics**
   - Token usage tracking
   - Cost analytics
   - Generation history

---

## 📚 API Documentation

### Projects

```
GET    /api/projects              # List all projects
POST   /api/projects              # Create project
GET    /api/projects/{id}         # Get project with artifacts
DELETE /api/projects/{id}         # Delete project
```

### Generation

```
POST   /api/generate              # Generate code
POST   /api/prompt/preview        # Preview prompt breakdown
POST   /api/prompt/text           # Get full prompt text
```

### Global RAG

```
POST   /api/global-rag/ingest     # Add knowledge
GET    /api/global-rag/retrieve   # Query knowledge
```

---

## 🎯 Key Differentiators vs Other AI Builders

| Feature | State RAG Builder | Others (Lovable, v0, etc.) |
|---------|------------------|----------------------------|
| **State Management** | Explicit State RAG per project | Implicit chat memory |
| **Authority System** | User > AI with file-level control | No explicit authority |
| **Prompt Transparency** | Full visibility into prompt | Black box |
| **File Selection** | Granular control over context | Auto-selected |
| **Token Awareness** | Real-time token/cost tracking | Hidden |
| **Isolation** | Per-project State RAG | Shared state |
| **Versioning** | Full artifact history | Limited |
| **Offline Mode** | Possible (local LLM) | Cloud-only |

---

## 📞 Support

If you encounter issues:
1. Check this guide
2. Review error messages in browser console (F12)
3. Check backend logs in terminal
4. Verify API keys are set correctly

---

## 🎉 You're Ready!

Your State RAG Builder is now set up with:
✅ Dual-pane interface (preview + code)
✅ Per-project State RAG isolation  
✅ Prompt visualization (signature feature)
✅ File selection with authority indicators
✅ Production-grade architecture

**Start building amazing websites with transparent AI! 🚀**
