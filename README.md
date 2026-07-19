# AI Incident Investigation Assistant

Local FastAPI + React dashboard for streaming, timestamp-normalized incident analysis.

## AI Support Engineer setup

The optional Step 3 uses the OpenAI Responses API with `gpt-5.4-mini` to review the same filtered **Entries TXT** content that is available for download. It sends the log entries and the optional issue context directly from the local backend; the browser never receives the API key.

Copy `backend/.env.example` to `backend/.env`, add your key, then restart the backend:

```dotenv
OPENAI_API_KEY=your_api_key_here
```

Log content is sent to OpenAI only when you choose **Get troubleshooting steps**.

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
