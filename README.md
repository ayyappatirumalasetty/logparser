# LogParser and AI Support Assistant

A powerful local FastAPI + React dashboard designed for real-time, timestamp-normalized log incident analysis. This tool scans directories of logs, automatically detects and parses varied timestamp formats, correlates events in a specified time window around an incident, and provides AI-powered troubleshooting advice.

---

## 🚀 Key Features

- **Secure Session Authentication:** JWT-based user session authentication protecting all backend endpoints and preventing unauthorized local analysis requests.
- **Automatic Timestamp Normalization:** Extensible parser that recognizes diverse log timestamp formats (Syslog, standard ISO formats, sub-second commas/dots, etc.) and aligns them to a uniform timeline.
- **High-Performance Scanning:** Fast, multi-threaded directory traversal and file parsing built on Python's `ThreadPoolExecutor` to handle multiple large log files concurrently.
- **Incident Correlated Timeline:** Filter events in a precise time window (e.g. ±60s) around a target timestamp to focus strictly on logs leading up to and immediately following the failure.
- **AI Support Engineer (Step 3):** Powered by OpenAI chat models to diagnose filtered log entries, identify root causes, and suggest structured troubleshooting steps while ensuring safety guardrails (credential redaction and prompt injection filters) are applied.
- **Real-Time NDJSON Streaming:** Streams scanning and parsing progress directly to the frontend for responsive feedback during large file processing.
- **Interactive UI Dashboard:** A premium, dark-mode dashboard built with React, Vite, and Lucide React featuring progress animations, severity indicators, keyword filters, and dynamic log previews.
- **Extensive Export Capabilities:** Download investigation reports in plain text, markdown, HTML, or structured PDF formats.

---

## 📂 Project Structure

```text
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── auth.py          # JWT-based login credentials & authorization guards
│   │   ├── guardrails.py    # Sanitization (credential redaction & injection guard)
│   │   ├── main.py          # FastAPI server, endpoints, static files mount
│   │   ├── models.py        # Pydantic schemas, safe path mapping
│   │   ├── parser.py        # Log parsing & timestamp regex engine
│   │   └── service.py       # Traversal, multi-threaded scanning, report builders
│   ├── tests/
│   │   ├── test_auth.py     # Integration tests for login and JWT validation
│   │   └── test_parser.py   # Unit tests for log parser format detection
│   └── requirements.txt     # Python dependencies
├── demo/
│   ├── Input/               # Sample log files
│   ├── generated/           # Tracked generated demo log files for testing
│   ├── generate_demo_logs.py# Script to generate random log failure scenarios
│   └── run_demo_tests.py    # Test suite for end-to-end flow
├── frontend/
│   ├── dist/                # Production build directory (gitignored)
│   ├── src/
│   │   ├── Login.tsx        # User authentication screen
│   │   ├── main.tsx         # React application logic and UI layout
│   │   ├── styles.css       # Custom HSL-tailored CSS variables and dashboard theme
│   │   └── vite-env.d.ts    # Vite environment declarations
│   ├── package.json         # Node scripts & packages
│   └── vite.config.ts       # Vite config
├── .env                     # Local environment file (ignored)
├── .env.example             # Environment template
├── .gitignore               # Global Git ignoring rules
├── Dockerfile               # Multi-stage production build configuration
└── README.md                # Project documentation
```

---

## 🛠️ Getting Started & Run Instructions

### Prerequisites
- Python 3.11+
- Node.js 20+
- (Optional) Docker

Copy the environment template and configure your keys and credentials:
```bash
cp .env.example .env
# Edit .env and enter:
# - OPENAI_API_KEY: Your OpenAI API key
# - ADMIN_USERNAME & ADMIN_PASSWORD: Credentials to log in to the dashboard (defaults: admin / admin123)
# - JWT_SECRET_KEY: Secret key for signing session tokens
```

---

### Option A: Run Locally (Development Mode)

#### 1. Start the FastAPI Backend
```bash
cd backend
python -m venv .venv
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 2. Start the Vite Frontend
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```

Open your browser to `http://localhost:5173`. Enter the log folder path (e.g. `D:\loganalyser\demo\generated` or `/app/demo/generated`) and target timestamp (e.g. matching the generated demo logs date/time) to begin.

---

### Option B: Run via Docker (Production Mode)

The project includes a multi-stage Docker configuration that builds the React frontend static assets and hosts them directly from the FastAPI backend.

#### 1. Build the Docker Image
```bash
docker build -t loganalyser .
```

#### 2. Run the Docker Container
Provide your OpenAI API key as an environment variable:
```bash
docker run -p 8000:8000 -e OPENAI_API_KEY="your-openai-api-key" loganalyser
```

Open `http://localhost:8000` to interact with the fully assembled application! (Note: When running inside Docker, the default folder path for demo logs resolves automatically to `/app/demo/generated`).

---

## 🤝 Codex & AI Collaboration Report

This project represents a close pair-programming collaboration between the human developer and **Codex by OpenAI with GPT-5.6**. Below is a breakdown of how this collaboration shaped the final implementation.

### ⚡ Where AI Accelerated the Workflow
- **Regex & Parsing Architecture:** Design and implementation of the extensible `TimestampParser` regex engine in `backend/app/parser.py`. AI expedited the generation of complex time-format capture patterns and the corresponding test cases in `backend/tests/test_parser.py`.
- **CSS Design Tokens:** AI generated the detailed CSS variable foundation in `frontend/src/styles.css`, establishing a modern, HSL-tailored palette with smooth transitions, cards, dynamic progress bars, and glowing active states.
- **Export Engines:** Building the ReportLab PDF rendering canvas in `backend/app/main.py`. Handling page margins, multi-line paragraph wrapping, page breaks, and canvas fonts dynamically was simplified with AI-drafted boilerplate code.
- **Dockerization Setup:** AI formulated the dual-stage build process which cleanly compiles the TS/React assets on lightweight Node containers and transfers the static files to python-slim, maintaining a minimal final image size.

### 🧠 Key Engineering & Product Decisions (Human-Led)
- **Path Isolation Guardrails:** Restricting backend path access. To prevent users from browsing arbitrary system files, the human developer enforced the `safe_path` constraint, rejecting any non-directory folders.
- **Windows-Linux Path Translation:** Because the React app defaults to a Windows path structure for local demo files, the developer added automated path translation inside `safe_path` so it transparently resolves to `/app/demo/generated` or `/app/temptes` when run in Linux containers (e.g. Docker, Railway, Render).
- **Graceful Headless Degradation:** Recognizing that the server-side Tkinter directory dialog in `/api/browse` will fail in headless cloud/container environments, the developer caught these exceptions, returned a `501 Not Implemented` code, and added user-facing alerts in React to handle it cleanly without crashing the container.
- **Input Guardrails & Redaction:** Added prompt injection checks and regex redaction logic for PII (IPs, credentials, keys) in `backend/app/guardrails.py` before passing raw logs to public API endpoints.

### 🤖 LLM Contribution to Final Product
- **Incident Diagnosis Reasoning:** The Step 3 AI Support Engineer utilizes the LLM as its reasoning core. The model parses the filtered entries and issue context, separates evidence from hypothesis, identifies root causes, and advises ordered remediation steps.
- **Interactive Assistance:** The assistant guided the developer through iterative UI refinements, backend structure cleanup (e.g. consolidating the double `.env` files into a single project root environment file), and verifying Git configuration hygiene.
