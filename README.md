# MyAIBOX

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white) ![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white) ![AWS](https://img.shields.io/badge/AWS-Bedrock%20%7C%20Strands_Agent-FF9900?logo=amazonwebservices&logoColor=white) ![Gemini](https://img.shields.io/badge/Google-Gemini-4285F4?logo=google&logoColor=white)

MyAIBOX (AI百宝箱) is a comprehensive Gen-AI application suite built with FastAPI and React. It provides access to various AI capabilities including AI Agent, multimodal chat, text processing, summarization, image/document recognition, and image creation.

## Overview

The application integrates multiple GenAI models (Bedrock, Gemini, OpenAI), with secure authentication via Amazon Cognito and session management backed by DynamoDB. It features a modular architecture with a React frontend communicating via AG-UI Protocol (SSE streaming).

🎉 **What's New in v3.9**
- **Models**: only the latest generation of each family — Claude 5.5 (Opus/Sonnet/Haiku) + Fable 5.1, GPT-6 (Astra/6.1 Sol/Luna), Grok 4.7, GLM 5.3, Kimi K3, Qwen3-VL, Nova 2.5 Sonic, Gemini 3.8 Flash; older generations are retired
- **Security**: MCP changes are admin-gated (`ADMIN_SUBS`); uploads are owner-scoped and size-limited (`MAX_UPLOAD_MB`)
- **Fixes**: models that reject `temperature`/`top_p`/`top_k` no longer fail when thinking is off; Chat works on Gemini, Nova and GPT-OSS again
- **Upgrading**: run `uv sync` and `my-aibox build`; apply the model changes in Settings → Models. See [CHANGELOG.md](CHANGELOG.md).

## Features

* **Chat** 💬 — Unified conversational AI: pick an agent (Assistant, Q&A persona, etc.), each with its own tools, skills, system prompt, and workspace
* **Text** 📝 — Proofreading, rewriting, reduction, expansion, multi-language support
* **Summary** 📰 — Document and text summarization
* **Talk** 🎙️ — Real-time voice conversation with a LiveAgent (`/talk/:agentId`)
* **Asking** 🧠 — Research-style deep Q&A: voice or text input, follow-up threads, per-question reasoning
* **Vision** 👀 — Image analysis, document understanding (PDF), multi-model support
* **Draw** 🎨 — AI image generation and editing with prompt optimization, style/ratio/seed options
* **Settings** ⚙️ — Account management, module configuration, model registry, MCP server management

Supported input formats: jpg/jpeg, png, gif, webp, pdf, csv, doc/docx, xls/xlsx, txt, md, mp4, webm, mov

## Screenshots

### Multimodal Chatbot
![my-aibox](/docs/screenshots/webchat.png "Multimodal Chatbot")

### Vision Recognition
![my-aibox](/docs/screenshots/vision.png "Vision Recognition")

### Generate and Edit
![my-aibox](/docs/screenshots/draw.png "Generate and Edit image")


### Settings
![my-aibox](/docs/screenshots/settings.png "Web UI")

## Project Structure

```
my-aibox/
├── app.py                        # FastAPI + uvicorn entry point
├── backend/                      # Backend Python modules
│   ├── api/                          # REST + SSE endpoints (chat, text, summary, asking, vision, draw, settings, upload)
│   ├── core/                         # Config, service layer, DynamoDB sessions
│   ├── common/                       # Auth, logger, CLI, provider cache, async stream
│   ├── genai/                        # LLM providers (Bedrock/Gemini/OpenAI), agents, tools
│   ├── utils/                        # AWS + Bedrock helpers
│   └── tests/                        # pytest unit + integration
├── frontend/                     # React SPA (Vite + TypeScript)
│   ├── src/                          # components / pages / api / styles
│   └── assets/                       # UI static assets (avatars, icons)
├── storage/                      # Runtime data (gitignored)
│   ├── uploads/                      # User-uploaded files
│   └── generated/                    # Generated images / videos
├── logs/                         # Application logs (gitignored)
├── deploy/                       # Deployment artifacts
│   ├── my-aibox.service              # systemd user unit template
│   ├── build-push.sh                 # build & push multi-arch image to ECR
│   └── full-stack/                   # Dockerfile + EKS reference (examples/)
├── docs/                         # README screenshots, etc.
├── pyproject.toml
├── CHANGELOG.md                  # Release history
└── README.md
```

## Tool & Skill System

| Type | Configuration | Examples |
|------|---------------|----------|
| **Strands Tools** | Per-agent toggle | `calculator`, `current_time`, `file_write` |
| **MCP Tools** | Settings → MCP Server | `exa-server`, `core-mcp-server` |
| **Legacy Tools** | Per-agent toggle | `get_weather`, `search_wikipedia` |
| **Skills** | Per-agent toggle (from `~/.agents/skills/`) | Anthropic-style skills loaded via Strands `AgentSkills` plugin |

MCP server types: HTTP, stdio, SSE. stdio servers run commands on the host, so adding one requires your Cognito `sub` in `ADMIN_SUBS` (when `ADMIN_SUBS` is set, all MCP changes are admin-only).

## Setup

1. Install dependencies:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

2. Configure environment:
```bash
aws configure
cp .env.example .env
# Edit .env: AWS region, Cognito, DynamoDB, API keys
```

3. Build frontend:
```bash
my-aibox build
```

4. Run:
```bash
uv run python app.py
```

## Routes

| Path | Description |
|------|-------------|
| `/` | React SPA (default → `/chat/assistant`) |
| `/login` | Login page |
| `/chat/:agentId` | Chat with the selected agent (e.g. `/chat/assistant`, `/chat/family_doctor`) |
| `/talk/:agentId` | Voice conversation (default `/talk/english-coach`) |
| `/text`, `/summary`, `/asking`, `/vision`, `/draw` | Tool modules |
| `/settings/session`, `/settings/agents`, `/settings/modules`, `/settings/models`, `/settings/mcp` | Settings pages |
| `/api/*` | Backend API |

## Deployment

### Local / EC2

```bash
my-aibox install            # set up the systemd user service (one-time)
my-aibox run                # run in the foreground (skips systemd)
my-aibox start|stop|restart # manage the systemd user service
my-aibox status             # show service status
my-aibox logs [-f]          # tail journalctl logs
my-aibox build              # build frontend (syncs version)
my-aibox check              # lint (ruff) + run unit tests
my-aibox test               # run pytest (default: tests/unit)
                            # use `my-aibox test -m integration` for real-service tests
```

### Container / EKS

The image in `deploy/full-stack/Dockerfile` is thin: it ships uv + git only, and the start script `git pull` the latest code at pod startup. So most code changes do not require a rebuild — just `kubectl rollout restart`.

```bash
deploy/build-push.sh           # build & push multi-arch (amd64 + arm64) to ECR
kubectl rollout restart deployment my-aibox   # roll pods, picks up latest commit + uv sync
```

`deploy/full-stack/examples/` contains reference IAM role/policy and a k8s manifest with our values baked in — copy them as a starting point, do not `kubectl apply` directly.

## License

MIT License - see LICENSE file for details
