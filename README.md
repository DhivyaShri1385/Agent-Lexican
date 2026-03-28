# AI-Based Image Generator with Custom Style Training

This project implements the full workflow:

Collect Images -> Train Model -> Build Backend -> Build UI -> Connect End-to-End

## 1. Project Goal (Pick One Theme)

Current project theme in config: `futuristic robots`

Use one theme only. Mixed styles reduce training quality.

You can change theme in `training/config.yaml` under `project.theme`.

## 2. Dataset Creation

Dataset layout:

```
dataset/
	images/
		img1.jpg
		img2.jpg
	captions/
		img1.txt
		img2.txt
```

Rules:

- 20 to 100 images
- Every image must have a matching caption file with the same filename stem
- Captions should describe the same visual style/theme

Example caption:

`a futuristic robot with glowing blue eyes in a neon city`

## 3. Model Training (LoRA Workflow)

### 3.1 Install dependencies

```powershell
pip install -r requirements.txt
```

### 3.2 Validate dataset and print command

```powershell
python training/train_lora.py --print-only
```

This script:

- validates image-caption pairs
- checks dataset size bounds
- creates `dataset/metadata.jsonl`
- prints the training launch command

### 3.3 Run training

Place the official Diffusers script at `training/train_text_to_image_lora.py`, then run:

```powershell
python training/train_lora.py
```

LoRA output will be saved to:

`model/lora`

## 4. Backend API

Backend is built with Flask and exposes:

- `GET /health`
- `GET /api/theme`
- `GET /api/history`
- `POST /api/generate`
- `POST /api/generate-async`
- `GET /api/jobs/<job_id>`
- `GET /outputs/<filename>`

Run backend:

```powershell
python -m backend.app
```

Single-app mode:

- Backend now serves frontend pages directly.
- Open `http://127.0.0.1:5000/login.html` or `http://127.0.0.1:5000/dashboard.html`.

## 5. Frontend

Frontend includes:

- Login/Register panel (email or user ID)
- GitHub login (OAuth, optional)
- Forgot password + reset token flow
- Prompt input
- Negative prompt
- Steps and guidance controls
- Generate action
- Download image button
- History panel
- Admin panel (users + generation analytics)

Authentication note:

- You must login before using generation/history endpoints.

Open frontend by serving `frontend/` with any static server.

Example with Python:

```powershell
python -m http.server 5500 -d frontend
```

Then open:

`http://localhost:5500`

Note:

- If you use frontend static server on port 5500, backend still runs on 5000.
- For production/self-host publish, use single-app mode via backend only.

Frontend module pages:

- `http://127.0.0.1:5500/login.html`
- `http://127.0.0.1:5500/dashboard.html`
- `http://127.0.0.1:5500/profile.html`
- `http://127.0.0.1:5500/settings.html`
- `http://127.0.0.1:5500/history.html`
- `http://127.0.0.1:5500/admin.html`

## Quick Start (One Click)

From project root, run either:

```powershell
.\start_servers.ps1
```

or

```powershell
.\start_servers.bat
```

This starts:

- Backend in a new PowerShell window
- Frontend static server in a new PowerShell window

URLs:

- Frontend: `http://127.0.0.1:5500`
- Backend health: `http://127.0.0.1:5000/health`

## Authentication APIs

- `GET /api/auth/me`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/github/login` (optional)
- `GET /api/auth/github/callback` (optional)
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`

Admin APIs:

- `GET /api/admin/users`
- `GET /api/admin/analytics`

Admin authorization:

- Set `ADMIN_EMAIL` environment variable.
- Any user with this email is promoted to admin role.

Local auth supports login by:

- email + password
- user ID + password

## GitHub OAuth Setup (Optional)

Set these environment variables before starting backend:

```powershell
$env:GITHUB_CLIENT_ID="your_client_id"
$env:GITHUB_CLIENT_SECRET="your_client_secret"
$env:FLASK_SECRET_KEY="replace-with-strong-random-secret"
$env:FRONTEND_URL="http://127.0.0.1:5500"
$env:BACKEND_URL="http://127.0.0.1:5000"
```

In your GitHub OAuth app, use callback URL:

`http://127.0.0.1:5000/api/auth/github/callback`

## Password Reset Email Setup

Set SMTP variables (recommended for production):

```powershell
$env:SMTP_HOST="smtp.gmail.com"
$env:SMTP_PORT="587"
$env:SMTP_USERNAME="your-email@example.com"
$env:SMTP_PASSWORD="your-app-password"
$env:SMTP_USE_TLS="true"
$env:MAIL_FROM="your-email@example.com"
```

Development behavior:

- If SMTP is not configured and `APP_ENV` is not `production`, the reset token is returned in API response as `reset_token_preview`.

You can start from `.env.example` for all required deployment variables.

## Deployment (Production)

### Render

- Use `render.yaml` at repository root.
- Set environment variables in Render dashboard:
	- `FLASK_SECRET_KEY`
	- `FRONTEND_URL`
	- `BACKEND_URL`
	- `ADMIN_EMAIL`
	- SMTP variables (for password reset emails)

### Railway

- `railway.json` is included.
- Start command uses Gunicorn.
- Set the same environment variables as Render.

### Azure App Service (Linux)

- Deploy this repository.
- Startup command:

```bash
bash azure/startup.sh
```

- Set the same environment variables in App Service Configuration.

Optional single-window mode:

```powershell
.\start_servers.ps1 -SameWindow
```

In `-SameWindow` mode servers run as background jobs:

- List jobs: `Get-Job`
- View logs: `Receive-Job -Name ai-backend -Keep`
- Stop servers: `Stop-Job -Name ai-backend,ai-frontend`

## 6. End-to-End Flow

1. User logs in (email/user ID/GitHub)
2. User enters prompt in frontend
3. Frontend calls backend `/api/generate`
4. Backend runs Stable Diffusion (+ optional LoRA weights)
5. Image is saved in `outputs/`
6. Image URL and metadata are returned to frontend
7. Frontend displays image and enables download

## 7. Notes

- If `model/lora` exists, backend tries to load LoRA weights.
- If LoRA is missing/invalid, backend falls back to base model.
- GPU is recommended for practical generation speed.

