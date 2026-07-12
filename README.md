# AI Interview Coach

AI Interview Coach is a Streamlit app that helps users practice interview questions, get STAR-based feedback on answers, and track interview readiness across sessions. It connects to IBM watsonx Orchestrate through IBM Cloud IAM authentication.

## What the app does

The app has three main parts:

1. Chat practice: ask interview questions or start a mock interview.
2. Feedback evaluation: paste an answer and get structured STAR feedback.
3. Dashboard: view readiness score, covered topics, and saved session history.

The app also lets the user set a candidate profile in the sidebar so responses can be personalized for name, role, experience level, and target company.

## How it works

1. `app.py` starts the Streamlit UI.
2. The user enters a message or selects a starter prompt.
3. `app.py` builds a context string from the sidebar profile.
4. `auth.py` gets an IBM Cloud IAM bearer token using `IAM_API_KEY`.
5. `agent.py` sends the request to watsonx Orchestrate and reads the SSE response stream.
6. The assistant response is shown in the chat or feedback tab.
7. Session data is stored in `sessions.json` so the dashboard can show past usage.

## Files that are necessary

### Required source files

- `app.py`: main Streamlit application, UI, tabs, state handling, readiness score, and session save logic.
- `agent.py`: connects to watsonx Orchestrate, sends chat requests, and parses streaming SSE responses.
- `auth.py`: generates the IBM Cloud IAM token needed before calling the agent API.
- `requirements.txt`: Python dependencies.
- `.streamlit/config.toml`: Streamlit theme and server settings.

### Required configuration

- `.env`: local environment variables. Create this by copying `env.example`.

### Optional / generated files

- `run.bat`: convenience launcher for Windows.
- `Dockerfile`: container build for deployment.
- `DEPLOYMENT.md`: deployment notes and examples.
- `_debug_agent.py`: debugging script for inspecting raw agent responses.
- `last_sse_response.txt`: debug output written by `agent.py` after a request.
- `sessions.json`: saved session history created by `app.py`.

## Project structure

```text
interview_agent/
├── app.py
├── agent.py
├── auth.py
├── requirements.txt
├── .streamlit/
│   └── config.toml
├── env.example
├── run.bat
├── Dockerfile
├── DEPLOYMENT.md
├── _debug_agent.py
└── .gitignore
```

## Setup

### 1. Create the environment file

Copy `env.example` to `.env` and fill in these values:

- `INSTANCE_URL`
- `AGENT_ID`
- `ENVIRONMENT_ID`
- `IAM_API_KEY`

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
streamlit run app.py
```

The app will usually open at `http://localhost:8501`.

On Windows, you can also use `run.bat`, which starts Streamlit on port `8503`.

## Environment variables

| Variable         | Purpose                                      |
| ---------------- | -------------------------------------------- |
| `INSTANCE_URL`   | Base watsonx Orchestrate instance URL        |
| `AGENT_ID`       | Target agent identifier                      |
| `ENVIRONMENT_ID` | Orchestrate environment identifier           |
| `IAM_API_KEY`    | IBM Cloud API key used to get a bearer token |

## Key behavior

- The sidebar stores a candidate profile and automatically expires it after 30 minutes.
- The first chat message can be combined with the profile context so the agent gets better interview prompts.
- `chat_with_agent()` writes the raw SSE payload to `last_sse_response.txt` for debugging.
- The dashboard calculates a readiness score from topic coverage, question count, and answer depth.
- Session history is appended to `sessions.json` and the most recent 50 sessions are kept.

## Deployment options

- Local development: run Streamlit directly.
- Docker: build from `Dockerfile` and pass the `.env` file at runtime.
- Streamlit Cloud: set the same variables in app secrets and deploy `app.py` as the main file.

## Notes

- Keep `.env`, `sessions.json`, and `last_sse_response.txt` out of source control.
- If the agent response is not parsed correctly, use `_debug_agent.py` to inspect the raw SSE stream.
