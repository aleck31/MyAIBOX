"""Claude on the Anthropic Messages API (Anthropic itself, or a gateway such as agw / Bedrock Mantle)."""
import asyncio
import base64
import json
from threading import Thread
from typing import Dict, Iterator, List, Optional

import anthropic

from backend.common.errors import blocked_reply_notice
from backend.genai.models import clients
from backend.genai.models.thinking import build_thinking_fields, rejects_sampling_params, rejects_stop_sequences
from backend.genai.tools.legacy.tool_registry import legacy_tool_registry
from backend.utils.file import FileProcessor
from . import LLMAPIProvider, LLMMessage, LLMParameters, LLMProviderError, LLMResponse
from .. import logger

_MAX_TOOL_ROUNDS = 8  # safety cap on the tool-use loop
_DEFAULT_MAX_TOKENS = 4096  # Messages requires max_tokens
# Messages refuses with stop_reason "refusal"; report it like a Bedrock content filter.
_STOP_REASON_MAP = {"refusal": "content_filtered"}
_MAX_FILE_SIZE = 5 * 1024 * 1024
_TEXT_DOCS = ("txt", "md", "csv")


class AnthropicMessagesProvider(LLMAPIProvider):
    """Streams text, thinking and tool use; runs legacy tools in a loop for modules like Asking."""

    def __init__(self, model_id: str, llm_params: LLMParameters, tools=None):
        super().__init__(model_id, llm_params, tools)
        self.llm_params: LLMParameters = llm_params

    def _validate_config(self) -> None:
        if not self.model_id:
            raise ValueError("Model ID must be specified for Anthropic Messages")

    def _initialize_client(self) -> None:
        self._model, provider = clients.resolve(self.model_id)
        self.client = anthropic.Anthropic(**clients.anthropic_client_args(provider))
        self.file_processor = FileProcessor(max_file_size=_MAX_FILE_SIZE)
        self._tool_defs = self._build_tool_defs() if self._model.capabilities.tool_use else []

    def _build_tool_defs(self) -> List[Dict]:
        defs = []
        for name in (self.tools or []):
            spec = legacy_tool_registry.get_tool_spec(name)
            if ts := (spec or {}).get('toolSpec'):
                defs.append({"name": ts["name"], "description": ts.get("description", ""),
                             "input_schema": ts.get("inputSchema", {}).get("json", {"type": "object", "properties": {}})})
        return defs

    def _exec_tool(self, name: str, args: Dict):
        """Run an async legacy tool from this sync generator via a background loop."""
        if not hasattr(self, '_bg_loop'):
            self._bg_loop = asyncio.new_event_loop()
            Thread(target=lambda: (asyncio.set_event_loop(self._bg_loop), self._bg_loop.run_forever()), daemon=True).start()
        return asyncio.run_coroutine_threadsafe(legacy_tool_registry.execute_tool(name, **args), self._bg_loop).result()

    def _handle_error(self, error: Exception):
        code = type(error).__name__
        logger.error(f"[AnthropicMessagesProvider] {code} - {error}")
        if isinstance(error, anthropic.RateLimitError):
            message = "Rate limit exceeded. Please try again later."
        elif isinstance(error, anthropic.AuthenticationError):
            message = "Authentication failed. Please check the provider's API key."
        elif isinstance(error, anthropic.NotFoundError):
            message = "This model is not available from its provider. Please choose another model."
        elif isinstance(error, anthropic.BadRequestError):
            message = "Invalid request format. Please try again with different input."
        elif isinstance(error, (anthropic.APITimeoutError, anthropic.APIConnectionError)):
            message = "Failed to reach the model provider. Please try again."
        else:
            message = "An unexpected error occurred. Please try again."
        raise LLMProviderError(code, message, str(error))

    # ── request building ─────────────────────────────────────────────────────

    def _file_blocks(self, files: List[str]) -> List[Dict]:
        blocks = []
        for path in files:
            kind, fmt = self.file_processor.get_file_type_and_format(path)
            data = self.file_processor.read_file(path, optimize=True)
            if kind == 'image':
                blocks.append({"type": "image", "source": {"type": "base64", "media_type": f"image/{fmt}",
                                                           "data": base64.b64encode(data).decode()}})
            elif fmt == 'pdf':
                blocks.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                              "data": base64.b64encode(data).decode()}})
            elif fmt in _TEXT_DOCS:
                name = self.file_processor.get_file_name(path)
                blocks.append({"type": "text", "text": f"File {name}:\n{data.decode('utf-8', errors='replace')}"})
            else:
                logger.warning(f"[AnthropicMessagesProvider] Skipped unsupported attachment: {path}")
        return blocks

    def _convert_message(self, msg: LLMMessage) -> Dict:
        blocks: List[Dict] = []
        if (ctx := getattr(msg, 'context', None)) and isinstance(ctx, dict):
            items = [f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in ctx.items() if v is not None]
            if items:
                blocks.append({"type": "text", "text": f"Context Information:\n{' | '.join(items)}\n"})
        content = msg.content
        if isinstance(content, str):
            if content.strip():
                blocks.append({"type": "text", "text": content.strip()})
        elif isinstance(content, dict):
            if text := (content.get("text") or "").strip():
                blocks.append({"type": "text", "text": text})
            blocks.extend(self._file_blocks(content.get("files") or []))
        return {"role": msg.role, "content": blocks}

    def _request(self, messages: List[LLMMessage], system_prompt: Optional[str], **kwargs) -> Dict:
        p = self.llm_params
        max_tokens = kwargs.get('max_tokens', p.max_tokens) or _DEFAULT_MAX_TOKENS
        req: Dict = {"model": self.model_id, "max_tokens": max_tokens,
                     "messages": [m for m in (self._convert_message(x) for x in messages) if m["content"]]}
        if system_prompt and system_prompt.strip():
            req["system"] = system_prompt
        thinking = kwargs.get('thinking', p.thinking)
        m = self._model
        fields = (build_thinking_fields(self.model_id, thinking, max_tokens)
                  if thinking and m.vendor == 'Anthropic' and m.capabilities.reasoning else {})
        if fields:
            # Thinking takes no sampling params and needs room beyond the reasoning budget.
            req.update(fields)
            budget = fields['thinking'].get('budget_tokens')
            req["max_tokens"] = max(max_tokens, budget * 2) if budget else max(max_tokens, 32000)
        elif not rejects_sampling_params(self.model_id):
            # Claude 4.5+ accepts temperature or top_p, not both.
            if (t := kwargs.get('temperature', p.temperature)) is not None:
                req["temperature"] = t
            elif (tp := kwargs.get('top_p', p.top_p)) is not None:
                req["top_p"] = tp
            if (k := kwargs.get('top_k', p.top_k)) is not None:
                req["top_k"] = k
        if (stop := kwargs.get('stop_sequences', p.stop_sequences)) and not rejects_stop_sequences(self.model_id):
            req["stop_sequences"] = stop
        if self._tool_defs:
            req["tools"] = self._tool_defs
        return req

    # ── generation ───────────────────────────────────────────────────────────

    def generate_content(self, messages: List[LLMMessage], system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        text = "".join(c.get('content', {}).get('text', '') for c in self.generate_stream(messages, system_prompt, **kwargs))
        return LLMResponse(content={"text": text}, metadata={'model': self.model_id})

    def generate_stream(self, messages: List[LLMMessage], system_prompt: Optional[str] = None, **kwargs) -> Iterator[Dict]:
        try:
            req = self._request(messages, system_prompt, **kwargs)
            for _round in range(_MAX_TOOL_ROUNDS + 1):
                if _round == _MAX_TOOL_ROUNDS:
                    # Out of tool rounds: answer from what was gathered instead of ending with no answer.
                    req["tool_choice"] = {"type": "none"}
                with self.client.messages.stream(**req) as stream:
                    for ev in stream:
                        if ev.type == 'content_block_start' and ev.content_block.type == 'tool_use':
                            yield {'tool_use': {'toolUseId': ev.content_block.id, 'name': ev.content_block.name}}
                        elif ev.type == 'content_block_delta' and ev.delta.type == 'text_delta':
                            yield {'content': {'text': ev.delta.text}}
                        elif ev.type == 'content_block_delta' and ev.delta.type == 'thinking_delta':
                            yield {'thinking': {'text': ev.delta.thinking}}
                    final = stream.get_final_message()

                stop_reason = _STOP_REASON_MAP.get(final.stop_reason, final.stop_reason)
                calls = [b for b in final.content if b.type == 'tool_use']
                if not calls or _round == _MAX_TOOL_ROUNDS:
                    if notice := blocked_reply_notice(stop_reason):
                        yield {'content': {'text': notice}}
                    yield {'metadata': {'stop_reason': stop_reason if not calls else 'max_tool_rounds',
                                        'usage': final.usage.model_dump()}}
                    return

                # The whole assistant turn goes back, thinking blocks (with signatures) included.
                req["messages"].append({"role": "assistant",
                                        "content": [b.model_dump(mode='json', exclude_none=True) for b in final.content]})
                results = []
                for c in calls:
                    try:
                        result = self._exec_tool(c.name, c.input or {})
                        results.append({"type": "tool_result", "tool_use_id": c.id,
                                        "content": result if isinstance(result, str) else json.dumps(result, default=str)})
                    except Exception as e:
                        results.append({"type": "tool_result", "tool_use_id": c.id, "is_error": True, "content": str(e)})
                req["messages"].append({"role": "user", "content": results})
        except LLMProviderError:
            raise
        except Exception as e:
            self._handle_error(e)

    def multi_turn_generate(self, message: LLMMessage, history: Optional[List[LLMMessage]] = None,
                            system_prompt: Optional[str] = None, **kwargs) -> Iterator[Dict]:
        yield from self.generate_stream([*(history or []), message], system_prompt, **kwargs)
