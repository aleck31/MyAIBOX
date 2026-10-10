# Changelog

All notable changes to MyAIBOX. The version lives in `pyproject.toml` (`my-aibox build` syncs it to the
frontend and lockfiles). The README only highlights the latest release.

## [3.9.0] - 2026-10-10

### Security
- **MCP servers**: changes are admin-gated. With `ADMIN_SUBS` set (comma-separated Cognito `sub`s), every MCP
  add/delete/toggle requires an admin; unset, adding **stdio** servers (which run commands on the host) is refused
  while http/sse stay open to any logged-in user.
- **Chat attachments** resolve only server-issued upload ids (`<uuid>.<ext>`). Client-supplied paths are dropped
  and logged; previously any `*.png/jpg` readable by the server could be attached.
- **Uploads** are streamed with a size limit (`MAX_UPLOAD_MB`, default 20 -> HTTP 413), checked against an
  extension allowlist, and **owner-scoped** (`<id>.owner` sidecar). Upload, vision and asking share one
  implementation (`backend/common/uploads.py`); the duplicate download route is merged and the missing `..` check
  on `GET /api/upload/{file_id}` is closed.

### Fixed
- Refreshed Cognito access tokens are now persisted to the session cookie (Cognito password mode only; SSO mode is
  unaffected). Previously users were signed out when the first token expired.
- `CORS_ORIGINS` defaults to same-origin instead of an unusable `*` that made startup fail. `*` is still rejected.
- `get_secret` parses Secrets Manager values as JSON, falling back to the legacy Python-repr format.
- Bare `pytest` no longer fails at collection without Cognito config; integration tests are only collected when
  requested (`-m integration`).
- Exceptions that were silently swallowed (Talk session teardown, MCP client stop, Settings tool listing) are logged.
- The EKS example manifest no longer ships a `SECRET_KEY` / `CORS_ORIGINS` the app refuses to start with.

### Changed
- **Backend dependencies** (`uv lock --upgrade`): strands-agents 1.59, openai 3, mcp 2, ag-ui-protocol 1.0,
  aws-sdk-* 0.12, fastapi, boto3, google-genai. Code adapted accordingly:
  - Voice input uses the new Transcribe streaming SDK with the CRT transport; credentials come from boto3 via
    `common/aws_identity.py` (the SDK's own chain has no EC2 instance-profile / container / web-identity support).
  - Talk moved to `strands.bidi` and its new event schema; a failed event stream now reaches the client as an
    error frame.
  - HTTP MCP servers use mcp 2's `streamable_http_client`.
  - ruff 0.17's wider default rule set is pinned back to the previous one.
- **Frontend dependencies**: vite 8, react-router 7, `@ag-ui/*` 1.x, `@types/node`; `npm audit` reports 0
  vulnerabilities. `vite.config.ts` is now type-checked by `npm run build`.
- EKS IAM example: adds `transcribe:StartStreamTranscription` and `bedrock:InvokeModelWithBidirectionalStream`,
  drops the unused `cognito-idp:Admin*` actions.

### Upgrade notes
1. `uv sync`, then `my-aibox build`.
2. Set `ADMIN_SUBS` (find your `sub` at `/api/auth/me`) to keep adding stdio MCP servers from Settings.
3. On EKS, add the two IAM permissions above to the pod role.
4. Files uploaded before 3.9 have no owner record and remain readable by any logged-in user.

### Not verified
OpenAI/Bedrock-Mantle with a real API key, Gemini live calls, and authenticated pages in a real browser.

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
