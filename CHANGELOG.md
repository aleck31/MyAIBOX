# Changelog

All notable changes to MyAIBOX. The version lives in `pyproject.toml` (`my-aibox build` syncs it to the
frontend and lockfiles). The README only highlights the latest release.

## [3.9.0] - 2026-10-10 ... [3.9.1] - 2026-10-10

### Added
- **Latest-generation models** (3.9.1): Claude Opus/Sonnet/Haiku 5.5 + Fable 5.1, GPT-6 Astra/6.1 Sol/Luna, Grok 4.7, GLM 5.3, Kimi K3, Qwen3-VL 235B, Nova 2.5 Sonic, Gemini 3.8 Flash.
- **`ADMIN_SUBS`** (3.9.0): MCP changes are admin-only; without it, stdio servers cannot be added.
- **Upload hardening** (3.9.0): attachments accept only server-issued ids; uploads are owner-scoped and size-limited (`MAX_UPLOAD_MB`, default 20).

### Changed
- **Models** (3.9.1): only the latest generation of each family is kept; Claude 4.x / Sonnet 5 / Fable 5, GPT-5.x, Grok 4.3, GLM 5, Qwen3 235B, Nova Pro, Nova 2 Sonic and Gemini 2.5/3.5 Flash are retired.
- **Dependencies** (3.9.0): strands 1.59, openai 3, mcp 2, ag-ui 1.0, aws-sdk 0.12; vite 8, react-router 7 (`npm audit` clean).

### Fixed (patch releases)
- 3.9.0 Refreshed Cognito tokens persist to the session cookie; `CORS_ORIGINS` defaults to same-origin; secrets parse as JSON.
- 3.9.1 Models that reject `temperature`/`top_p`/`top_k` (Claude 4.7+, Grok 4.7, Kimi K3, GPT-5/6) no longer fail when thinking is off; Opus 5.x and Haiku 5.5 use adaptive thinking.
- 3.9.1 Chat works on Gemini, Nova 2 Lite and GPT-OSS again; `.env` is loaded from the project root.

### Upgrade notes
`uv sync` and `my-aibox build`; set `ADMIN_SUBS` to keep adding stdio MCP servers; apply the model changes in Settings -> Models (the registry is in DynamoDB); on EKS add `transcribe:StartStreamTranscription` and `bedrock:InvokeModelWithBidirectionalStream` to the pod role.

## [3.8.0] - 2026-05-31 ... [3.8.12] - 2026-07-01

### Added
- **Talk**: real-time voice conversation with a LiveAgent (Nova Sonic speech-to-speech) at `/talk/:agentId`, e.g.
  an English-practice coach with multi-level coaching; voice and model switching (3.8.0, 3.8.3).
- **More models**: GPT-5 and Grok via Bedrock Mantle (Responses API), Claude adaptive-thinking models, Sonnet 5
  (3.8.6, 3.8.8, 3.8.9, 3.8.11).
- **Chat persistence**: conversations survive a page refresh; cloud sync is independent (3.8.5).

### Fixed (patch releases)
- 3.8.1 Talk transcript persists across route switches; front/back history stay consistent.
- 3.8.4 LiveAgent tool use works; spoken answers are concise.
- 3.8.7 GPT-5 returning nothing in Asking; errors with reasoning models.
- 3.8.9 / 3.8.10 / 3.8.11 Grok on Mantle: base URL default, duplicate tool calls and replies, thinking indicator;
  Asking voice transcription.
- 3.8.12 A stale selected model is dropped when it is disabled or removed.

## [3.7.0] - 2026-05-30
- **Voice input (Asking)**: speak your question; live transcription via AWS Transcribe streaming, with optional
  auto-send.
- **Research-style Asking**: questions and follow-ups stack as a scrollable thread (numbered Q/A blocks with
  collapsible reasoning), plus a resizable rail that indexes every question.
- 3.7.1-3.7.5: Lucide icons, tools wired into Asking with progress, module-default model honoured, user-configurable
  thinking, delete-and-re-ask with per-round cards.

## [3.6.0] - 2026-05-23
- **Models enable/disable**: toggle individual models off in Settings -> Models without deleting them.
- **Per-agent inference parameters**: `temperature` / `top_p` / `max_tokens` configured in Agents settings are now
  actually applied.
- **Tool progress hints**: long-running tools (e.g. `file_write`) no longer make the UI look frozen.
- **MCP health check**: cached agent providers verify MCP sessions and rebuild on dead connections.
- Deploy reorganisation and cleanup.

## [3.5.0] - 2026-05-09
- **Unified Chat module**: Assistant + Persona merged into a single `/chat/:agentId` route; each agent = system
  prompt + tools + params + skills.
- **Strands-native Skills**: agents can load Anthropic-style skills via the `AgentSkills` plugin (requires
  `strands-agents>=1.39`).
- **Per-agent workspace**: isolated at `storage/workspace/<username>/<agent_id>/`.
- **Configurable agents**: override model, parameters, tools and skills per agent (persisted in DynamoDB).
- Message avatars and installable PWA (3.5.3).
- **Breaking**: `/assistant` and `/persona` redirect to `/chat/assistant`; `/api/assistant/*` and
  `/api/persona/*` are replaced by `/api/chat/*`.

## [3.2.0] - 2026-03
- **Agent session cache**: per-session Strands Agent caching with 2h TTL, hot-swap model, persistent MCP connections.
- **Multimodal chat**: file attachments and image display in agent conversations.
- **Image editing**: edit images with text instructions (Gemini, Nova Canvas, Stability AI).
- **Shared SSE parser**: unified `readSSE()` with proper line buffering, fixing stream truncation across modules.
- **CLI tools**: `my-aibox build` (with automatic version sync) and `my-aibox check` (ruff linting).

## [3.0.0] - 2026-02-24
- **React frontend**: full migration from Gradio to React + AG-UI Protocol with SSE streaming.
- **Generative UI**: dual-track streaming (chain-of-thought reasoning + tool-use UI).
- **Model & MCP management**: in-app model registry and MCP server configuration.

## [2.x]
- **Multi-provider agent**: Bedrock, Gemini and OpenAI models via the Strands SDK.
