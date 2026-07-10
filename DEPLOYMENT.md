# AI Interview Coach – Deployment Guide

## Project Structure

```
interview_agent/
├── app.py                  # Streamlit main application
├── auth.py                 # IBM Cloud IAM token helper
├── agent.py                # watsonx Orchestrate streaming chat client
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build file
├── env.example             # → rename to .env before running locally
├── gitignore.example       # → rename to .gitignore before git init
└── .streamlit/
    └── config.toml         # Streamlit theme & server settings
```

---

## Option 1 – Run Locally

### Prerequisites
- Python 3.11+
- pip

### Steps

```bash
# 1. Enter the project folder
cd interview_agent

# 2. Rename the example env file
cp env.example .env          # macOS/Linux
copy env.example .env        # Windows CMD

# 3. (Optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
.venv\Scripts\activate       # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

Test message: `I am a Fresher Software Engineer. Give me 5 technical questions.`

---

## Option 2 – Docker

```bash
# Build the image
docker build -t interview-coach .

# Run (pass .env file)
docker run --env-file .env -p 8501:8501 interview-coach
```

Open **http://localhost:8501**.

---

## Option 3 – Streamlit Community Cloud (Fastest, Free)

1. **Push to GitHub**
   ```bash
   git init
   cp gitignore.example .gitignore   # ensures .env is NOT committed
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/<your-user>/<your-repo>.git
   git push -u origin main
   ```

2. Go to **https://share.streamlit.io** → "New app"

3. Select your repository and set **Main file path** to `app.py`

4. Open **Advanced settings → Secrets** and add:
   ```toml
   INSTANCE_URL   = "https://api.<region>.watson-orchestrate.cloud.ibm.com/instances/<your-instance-id>"
   AGENT_ID       = "<your-agent-id>"
   ENVIRONMENT_ID = "<your-environment-id>"
   IAM_API_KEY    = "<your-ibm-cloud-api-key>"
   ```

5. Click **Deploy** – your public URL is ready in ~2 minutes.

> **Note:** Streamlit Cloud secrets are accessible via `os.getenv()` the same
> way `.env` variables are, so no code changes are needed.

---

## Environment Variables Reference

| Variable         | Description                                   |
|------------------|-----------------------------------------------|
| `INSTANCE_URL`   | watsonx Orchestrate instance base URL         |
| `AGENT_ID`       | Target agent identifier                       |
| `ENVIRONMENT_ID` | Deployment environment identifier             |
| `IAM_API_KEY`    | IBM Cloud API key for IAM token generation    |

---

## Architecture

```
Browser
  │
  ▼
Streamlit app.py
  ├── auth.py  →  POST https://iam.cloud.ibm.com/identity/token
  │                    (exchanges API key for Bearer token, cached 50 min)
  │
  └── agent.py →  POST {INSTANCE_URL}/v1/orchestrate/runs?stream=true…
                       (SSE stream parsed; thread_id maintained per session)
```
