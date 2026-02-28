# MyAIBOX

MyAIBOX (AI百宝箱) is a comprehensive Gen-AI application suite built with FastAPI and React. It provides access to various AI capabilities including AI Agent, multimodal chat, text processing, summarization, image/document recognition, and image creation.

## Overview

The application integrates multiple GenAI models (Bedrock, Gemini, OpenAI), with secure authentication via Amazon Cognito and session management backed by DynamoDB. It features a modular architecture with a React frontend communicating via AG-UI Protocol (SSE streaming).

🎉 **What's New in v3.2**
- **Agent Session Cache**: Per-session Strands Agent caching with 2h TTL, hot-swap model, persistent MCP connections
- **Assistant Multimodal**: File attachments and image display in Agent conversations
- **Image Editing**: Edit images with text instructions (Gemini, Nova Canvas, Stability AI)
- **CLI Tools**: `my-aibox build` (with auto version sync) and `my-aibox check` (ruff linting)

**v3.0**
- **React Frontend**: Full migration from Gradio to React + AG-UI Protocol with SSE streaming
- **Generative UI**: Assistant module supports dual-track streaming (CoT reasoning + tool use UI)
- **Model & MCP Management**: In-app model registry and MCP server configuration

**v2.x**
- **AgentCore Runtime**: Serverless AI Agent on AWS Bedrock AgentCore Runtime (up to 8 hours, SSE streaming)
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

### Main Interface
![my-aibox](/assets/screenshot.png "Web UI")

### Multimodal Chatbot
![my-aibox](/assets/screenshot_chatbot.png "Multimodal Chatbot")

### Vision Recognition
![my-aibox](/assets/screenshot_vision.png "Vision Recognition")

## Project Structure

```
my-aibox/
├── app.py                        # FastAPI entry point
├── api/                          # REST + SSE API endpoints
│   ├── auth.py                       # Authentication & session management
│   ├── assistant.py                  # Assistant (AG-UI SSE + tool use)
│   ├── persona.py                    # Persona chat (AG-UI SSE)
│   ├── text.py                       # Text processing (SSE)
│   ├── summary.py                    # Summarization (SSE)
│   ├── asking.py                     # Reasoning (SSE with thinking)
│   ├── vision.py                     # Vision analysis (SSE)
│   ├── draw.py                       # Image generation (REST)
│   ├── settings.py                   # Settings, models, MCP CRUD
│   └── upload.py                     # File upload
├── frontend/                     # React SPA
│   └── src/
│       ├── components/               # UI components (ChatWindow, Processors, Panels)
│       ├── pages/                    # Route pages
│       ├── api/client.ts             # API client
│       └── styles/                   # CSS modules
├── core/                         # Core components
│   ├── config.py                     # Configuration
│   ├── module_config.py              # Module configuration
│   ├── service/                      # Service layer (GenService, ChatService, AgentService, DrawService)
│   └── session/                      # Session management (DynamoDB)
├── common/                       # Auth (Cognito), logging
├── genai/                        # GenAI integration
│   ├── models/                       # LLM providers (Bedrock, Gemini, OpenAI)
│   ├── agents/                       # Strands Agent + AgentCore client
│   └── tools/                        # Legacy tools, MCP tools, unified provider
├── agentcore_app.py              # AgentCore Runtime entry point
└── devguide/                     # Development guides
```

## Tool System

| Tool Type | Configuration | Examples |
|-----------|---------------|----------|
| **Legacy Tools** | Module Configuration | `get_weather`, `search_wikipedia` |
| **Strands Tools** | Always enabled | `calculator`, `current_time` |
| **MCP Tools** | Settings → MCP Server | `exa-server`, `core-mcp-server` |

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
my-aibox start    # start in background (tmux)
my-aibox stop     # stop
my-aibox restart  # restart
my-aibox status   # check status
my-aibox attach   # view live output (Ctrl+B D to detach)
my-aibox build    # build frontend
my-aibox check    # lint Python code (ruff)
```

### AgentCore Runtime (Serverless Agent)
```bash
.venv/bin/agentcore deploy

# .env
USE_AGENTCORE=true
AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:...
```


## License

MIT License - see LICENSE file for details
