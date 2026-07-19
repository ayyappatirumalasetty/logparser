# AI Incident Investigation Assistant

Local FastAPI + React dashboard for streaming, timestamp-normalized incident analysis.

## Run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Enter an accessible directory path and a target timestamp such as `23.01.26 13:16:11`.
