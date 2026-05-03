# MyAIBOX

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white) ![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white) ![AWS](https://img.shields.io/badge/AWS-Bedrock%20%7C%20Strands_Agent-FF9900?logo=amazonwebservices&logoColor=white) ![Gemini](https://img.shields.io/badge/Google-Gemini-4285F4?logo=google&logoColor=white)

MyAIBOX (AI百宝箱) is a comprehensive Gen-AI application suite built with FastAPI and React. It provides access to various AI capabilities including AI Agent, multimodal chat, text processing, summarization, image/document recognition, and image creation.

## Overview

The application integrates multiple GenAI models (Bedrock, Gemini, OpenAI), with secure authentication via Amazon Cognito and session management backed by DynamoDB. It features a modular architecture with a React frontend communicating via AG-UI Protocol (SSE streaming).

🎉 **What's New in v3.2**
- **Agent Session Cache**: Per-session Strands Agent caching with 2h TTL, hot-swap model, persistent MCP connections
- **Assistant Multimodal**: File attachments and image display in Agent conversations
- **Image Editing**: Edit images with text instructions (Gemini, Nova Canvas, Stability AI)
- **Shared SSE Parser**: Unified `readSSE()` with proper line buffering, fixing stream truncation across modules
- **CLI Tools**: `my-aibox build` (with auto version sync) and `my-aibox check` (ruff linting)

**v3.0**
- **React Frontend**: Full migration from Gradio to React + AG-UI Protocol with SSE streaming
- **Generative UI**: Assistant module supports dual-track streaming (CoT reasoning + tool use UI)
- **Model & MCP Management**: In-app model registry and MCP server configuration

**v2.x**
- **Multi-provider Agent**: Bedrock, Gemini, and OpenAI models via Strands SDK

## Features

* **Assistant** 🤖 — Agentic AI assistant with tool use, Generative UI, multimodal input, and cloud sync
* **Persona** 💬 — Multimodal Chatbot with personality profiles, file attachments, context-aware conversations
* **Text** 📝 — Proofreading, rewriting, reduction, expansion, multi-language support
* **Summary** 📰 — Document and text summarization
* **Asking** 🧠 — Deep reasoning with thinking + text dual-channel streaming
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
│   ├── api/                          # REST + SSE endpoints (assistant, persona, text,
│   │                                 #   summary, asking, vision, draw, settings, upload)
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
│   └── full-stack/                   # Dockerfile + IAM + K8s manifests
├── docs/                         # README screenshots, etc.
├── pyproject.toml
└── README.md
```

## Tool System

| Tool Type | Configuration | Examples |
|-----------|---------------|----------|
| **Strands Tools** | Always enabled | `calculator`, `current_time` |
| **MCP Tools** | Settings → MCP Server | `exa-server`, `core-mcp-server` |
| **Legacy Tools** | Module Configuration | `get_weather`, `search_wikipedia` |

MCP server types: HTTP, stdio, SSE.

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
| `/` | React SPA (default → `/assistant`) |
| `/login` | Login page |
| `/assistant`, `/persona`, `/text`, `/summary`, `/asking`, `/vision`, `/draw` | Feature modules |
| `/settings`, `/models`, `/mcp` | Settings pages |
| `/api/*` | Backend API |

## Deployment

### Local / EC2

```bash
my-aibox install           # set up the systemd user service (one-time)
my-aibox run               # run in the foreground (skips systemd)
my-aibox start|stop|restart # manage the systemd user service
my-aibox status            # show service status
my-aibox logs [-f]         # tail journalctl logs
my-aibox build             # build frontend (syncs version)
my-aibox check             # lint (ruff) + run unit tests
my-aibox test              # run pytest (default: tests/unit)
                           # use `my-aibox test -m integration` for real-service tests
```

## License

MIT License - see LICENSE file for details
