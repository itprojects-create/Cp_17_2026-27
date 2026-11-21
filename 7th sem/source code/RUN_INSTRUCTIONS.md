# Run Instructions

Step-by-step setup for running NovaByte locally. For a project overview, see the [README](README.md).

- [Prerequisites](#prerequisites)
- [1. Get the code](#1-get-the-code)
- [2. Configure the backend](#2-configure-the-backend)
- [3. Start the backend](#3-start-the-backend)
- [4. Start the frontend](#4-start-the-frontend)
- [5. Sign in](#5-sign-in)
- [6. Verify the installation](#6-verify-the-installation)
- [Sending real email](#sending-real-email)
- [Running with Docker](#running-with-docker)
- [Troubleshooting](#troubleshooting)

## Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11 or newer |
| Node.js | 20 or newer (with npm) |
| Git | any recent version |

You also need an API key for at least one language-model provider:

- **NVIDIA API Catalog** (primary): create a key at [build.nvidia.com](https://build.nvidia.com)
- **Google Gemini** (fallback): create a key at [aistudio.google.com](https://aistudio.google.com/apikey)

With only one key, that provider is used on its own. With neither, chat and *Ask AI* still run but can only show document excerpts (see [Troubleshooting](#chat-replies-the-configured-language-model-provider-is-unavailable)).

## 1. Get the code

```bash
git clone https://github.com/CMPN-CODECELL/Syrus2026_CodeCraft.git
cd Syrus2026_CodeCraft
```

## 2. Configure the backend

Create your local environment files from the templates:

**Windows (PowerShell)**

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

**macOS / Linux**

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Then edit `backend/.env` and set your keys:

```ini
LLM_PROVIDER=nvidia
LLM_FALLBACK_PROVIDER=gemini

NVIDIA_API_KEY=nvapi-...
GOOGLE_API_KEY=...
GEMINI_API_KEY=...
```

Paste the key exactly as shown on the NVIDIA site. It starts with `nvapi-`; do not include the `Bearer ` prefix from NVIDIA's curl examples.

### Choosing an NVIDIA model

`NVIDIA_MODEL` must be a **model ID** from the catalog (`vendor/model-name`), not the display name shown on the website. These free-tier models were tested with this app's grounded prompts:

| Model ID | Typical latency | Notes |
|---|---|---|
| `nvidia/nemotron-3.5-lightning-30b-a3b` | ~1.5 s | **Recommended default.** Natural explanations, follows grounding rules |
| `nvidia/nemotron-3.5-bolt-e4b` | ~1 s | Fastest; smaller model that tends to restate the docs verbatim |
| `openai/gpt-oss-20b` | ~6 s | Richest formatting; noticeably slower |

Model availability depends on your NVIDIA account. To list the IDs your key can see:

```bash
curl https://integrate.api.nvidia.com/v1/models
```

Everything else can stay at its default for local development. Integrations (`EMAIL_MODE`, `GITHUB_MODE`) default to `mock`, so no external services are contacted. Mock emails are written to `backend/sent_emails/`.

## 3. Start the backend

Open **terminal 1**:

```bash
cd backend
pip install -r requirements.txt
python run.py
```

> **Tip:** use a virtual environment (`python -m venv .venv`, then activate it with `.venv\Scripts\Activate.ps1` on Windows or `source .venv/bin/activate` on macOS/Linux) before installing.

On first start the backend creates the SQLite database, seeds the demo accounts, indexes the knowledge base into ChromaDB and loads the embedding model. This takes roughly 15–30 seconds; later starts are faster.

| URL | Purpose |
|---|---|
| http://localhost:8000/health | Health check |
| http://localhost:8000/docs | Interactive API documentation |
| http://localhost:8000/api/system/llm-status | Active LLM provider and fallback |

## 4. Start the frontend

Open **terminal 2**:

```bash
cd frontend
npm install
npm run dev
```

The app is served at **http://localhost:5173**.

## 5. Sign in

In debug mode (the default) these demo accounts are created automatically:

| Role | Username | Email | Password |
|---|---|---|---|
| Employee | `demo_user` | `demo@novabyte.dev` | `DemoPass123!` |
| HR admin | `demo_hr` | `demo_hr@novabyte.dev` | `DemoPass123!` |

New accounts created through **Sign up** are employees. To try the onboarding flow from scratch, sign up and introduce yourself in **AI Chat**, for example: *"Hi, I'm a backend intern working with Node.js."*

## 6. Verify the installation

From the repository root:

```bash
# Backend: 107 tests, no API keys needed (uses a deterministic mock model)
python -m pytest backend/tests -q

# Frontend: lint, type-check and production build
cd frontend
npm run lint
npm run build
```

`make verify` runs the backend tests and the frontend build together. Other Makefile targets: `make test-all` (verbose backend tests) and `make test-golden` (agent golden cases).

## Sending real email

By default `EMAIL_MODE=mock` writes emails to `backend/sent_emails/` instead of sending them. To send real email (password resets and HR completion reports), configure SMTP in `backend/.env`.

**Gmail (simplest):**

1. Turn on [2-Step Verification](https://myaccount.google.com/security) for the Google account.
2. Create an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords). Your normal password will not work.
3. Set:

```ini
EMAIL_MODE=real
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop      # the App Password; spaces are fine
SMTP_FROM_NAME=NovaByte Onboarding
HR_EMAIL=hr-inbox@yourcompany.com      # a real inbox that should receive completion reports
```

**Other providers:** use the provider's SMTP host, port and credentials. Port `587` uses STARTTLS; port `465` uses SSL automatically. `SMTP_FROM_EMAIL` defaults to `SMTP_USER` and must be that account or a verified alias.

**Test it** before restarting the app:

```bash
cd backend
python scripts/send_test_email.py you@example.com
```

The script logs in, sends one email and explains any failure (rejected login, unreachable server, refused sender). Then restart the backend. **Integrations → Email Notifications → Connect** now performs a real login and shows *Connected* only when the credentials work.

> Recipients must be real addresses. The demo accounts use `@novabyte.dev` emails, so password-reset mail for them will bounce; sign up with your own address to test the reset flow.

## Running with Docker

With `backend/.env` configured:

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |

API keys are read from `backend/.env` at runtime; the file is excluded from the built images.

## Troubleshooting

### `ModuleNotFoundError: No module named 'app'`

Start the backend from inside the `backend/` directory:

```bash
cd backend
python run.py
```

### Port 8000 or 5173 is already in use

A previous server is still running. Find and stop it:

**Windows (PowerShell)**

```powershell
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

**macOS / Linux**

```bash
lsof -ti :8000 | xargs kill
```

### Chat replies "The configured language-model provider is unavailable"

No working LLM is configured. Check `GET http://localhost:8000/api/system/llm-status` or **Settings → AI Engine & LLM** in the app:

- `"error": "...NVIDIA_API_KEY missing..."`: add `NVIDIA_API_KEY` to `backend/.env` and restart the backend.
- `401 Unauthorized` from NVIDIA: the key is wrong or expired. Generate a new one at [build.nvidia.com](https://build.nvidia.com).
- `404 Not Found` / `Function ... Not found for account`: the model ID doesn't exist or isn't available to your account. Pick one from the [tested models](#choosing-an-nvidia-model).
- `429 RESOURCE_EXHAUSTED` in the backend log: the Gemini key is out of quota. Add an NVIDIA key or wait for the quota to reset.

When the primary provider fails on a request, the fallback is tried automatically; restart the backend after changing any key.

### Knowledge Base *Ask AI* shows "Relevant excerpts" instead of an answer

The knowledge base search is working but no LLM is available, so the matching passages are shown verbatim. Configure a provider as described above.

### The first question after starting the backend is slow

The embedding model loads in the background during startup. Wait until the backend log shows the model loaded (about 15 seconds on first run) before sending the first question.

### Checking which LLM is active

```bash
# macOS / Linux
curl http://localhost:8000/api/system/llm-status

# Windows PowerShell
Invoke-RestMethod http://localhost:8000/api/system/llm-status
```

### Resetting local data

Stop the backend and delete `backend/onboarding.db` (application data) and/or `backend/chroma_db/` (search index). Both are recreated on the next start, including the demo accounts.
