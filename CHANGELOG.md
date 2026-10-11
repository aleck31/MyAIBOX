# Changelog

All notable changes to MyAIBOX. The version lives in `pyproject.toml` (`my-aibox build` syncs it to the
frontend and lockfiles). The README only highlights the latest release.

## [3.9.0] - 2026-10-10 ... [3.9.5] - 2026-10-11

### Added
- **Latest-generation models** (3.9.1): Claude Opus/Sonnet/Haiku 5.5 + Fable 5.1, GPT-6 Astra/6.1 Sol/Luna, Grok 4.7, GLM 5.3, Kimi K3, Qwen3-VL 235B, Nova 2.5 Sonic, Gemini 3.8 Flash.
- **`ADMIN_SUBS`** (3.9.0): MCP changes are admin-only; without it, stdio servers cannot be added.
- **Upload hardening** (3.9.0): attachments accept only server-issued ids; uploads are owner-scoped and size-limited (`MAX_UPLOAD_MB`, default 20).
- **Hideable sidebar** (3.9.5): a button at the top of the desktop sidebar hides it, the menu button brings it back; the choice is remembered.
- **Replies survive a dropped connection** (3.9.5): switching app, locking the phone or reloading no longer loses a Chat or Asking reply; the page re-attaches to it.

### Changed
- **Models** (3.9.1): only the latest generation of each family is kept; Claude 4.x / Sonnet 5 / Fable 5, GPT-5.x, Grok 4.3, GLM 5, Qwen3 235B, Nova Pro, Nova 2 Sonic and Gemini 2.5/3.5 Flash are retired.
- **Dependencies** (3.9.0): strands 1.59, openai 3, mcp 2, ag-ui 1.0, aws-sdk 0.12; vite 8, react-router 7 (`npm audit` clean).

### Fixed (patch releases)
- 3.9.0 Refreshed Cognito tokens persist to the session cookie; `CORS_ORIGINS` defaults to same-origin; secrets parse as JSON.
- 3.9.1 Models that reject `temperature`/`top_p`/`top_k` (Claude 4.7+, Grok 4.7, Kimi K3, GPT-5/6) no longer fail when thinking is off; Opus 5.x and Haiku 5.5 use adaptive thinking.
- 3.9.1 Chat works on Gemini, Nova 2 Lite and GPT-OSS again; `.env` is loaded from the project root.
- 3.9.2 A model that keeps re-calling a tool no longer runs for minutes: an agent turn stops after 90 model calls (`AGENT_MAX_CYCLES`).
- 3.9.2 `current_time` is a local tool; the Strands one is deprecated and logged a warning on every call.
- 3.9.2 A retired model id (e.g. from a page opened before a model upgrade) now reports which model is unavailable and to refresh, instead of a generic error.
- 3.9.3 Chat composer: Send and Stop share one icon button and a reply with THINKING/tool bars keeps one width; the UI now meets the lab visual baseline (sidebar, chevron and Talk-button text >= 4.5:1 contrast, every control >= 42px on touch).
- 3.9.4 Chat works on every model again: models that reject stop sequences (DeepSeek, GPT-OSS, Grok 4.7, Kimi K3, Qwen3-VL) and mid-conversation model switches (8 of 16 models) no longer fail, server errors show instead of an empty bubble, and a page whose model was retired reloads its model list and re-picks. Text sends the model picked after typing. Draw: Nova Canvas removed (AWS Legacy, always failed). UI: scrollable top bars fade their right edge, disabled controls keep >= 5:1 contrast; Settings -> MCP drops the always-1 Tools column.
- 3.9.5 Images and files sent in Chat reach the model again (dropped since 3.9.0; pages from before 3.9.0 got a 422). Chat and Asking no longer abort on Sonnet/Grok with "No active reasoning message" and a following "Agent is already processing a request"; after Stop the next message answers at once instead of redoing the stopped request. When the provider's content filter blocks a reply (Claude after some searches) it is retried once, then explained. UI: new app icon; one top-bar height with the menu button centred; touch controls drawn at 36px with a 42px hit area.

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
