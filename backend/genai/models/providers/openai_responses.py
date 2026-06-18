import asyncio
import json
from threading import Thread
from typing import Dict, List, Optional, Iterator
import openai
from openai import OpenAI
from backend.core.config import env_config
from backend.utils.aws import get_secret
from backend.genai.models.model_manager import model_manager
from backend.genai.tools.legacy.tool_registry import legacy_tool_registry
from . import LLMAPIProvider, LLMParameters, LLMMessage, LLMResponse, LLMProviderError
from .. import logger

_MAX_TOOL_ROUNDS = 8  # safety cap on the tool-use loop


class OpenAIResponsesProvider(LLMAPIProvider):
    """OpenAI-compatible models on the Responses API (e.g. GPT-5 via Bedrock Mantle).

    Same wire protocol as OpenAIProvider but uses the Responses API and a per-model
    base_url + Bedrock API key, since GPT-5 rejects /chat/completions. Supports a
    tool-use loop (legacy tools) for modules like Asking.
    """

    def __init__(self, model_id: str, llm_params: LLMParameters, tools=None):
        super().__init__(model_id, llm_params, tools)
        self.llm_params: LLMParameters = llm_params

    def _validate_config(self) -> None:
        if not self.model_id:
            raise ValueError("Model ID must be specified for OpenAIResponses")

    def _initialize_client(self) -> None:
        try:
            model = model_manager.get_model_by_id(self.model_id)
            if not model:
                raise ValueError(f"Model {self.model_id} not found")
            base_url = getattr(model, 'base_url', '') or env_config.mantle_base_url
            secret_id = env_config.bedrock_config.get('secret_id')
            api_key = get_secret(secret_id).get('api_key') if secret_id else None
            if not api_key:
                raise ValueError("Bedrock API key not configured (Secrets Manager)")
            self.client = OpenAI(base_url=base_url, api_key=api_key)
            self._tool_defs = self._build_tool_defs()
        except Exception as e:
            raise ValueError(f"Failed to initialize OpenAIResponses client: {str(e)}")

    def _build_tool_defs(self) -> List[Dict]:
        """Convert enabled tools' Bedrock toolSpec into Responses function defs."""
        defs: List[Dict] = []
        for name in (self.tools or []):
            spec = legacy_tool_registry.get_tool_spec(name)
            ts = spec.get('toolSpec') if spec else None
            if not ts:
                continue
            defs.append({
                "type": "function",
                "name": ts["name"],
                "description": ts.get("description", ""),
                "parameters": ts.get("inputSchema", {}).get("json", {"type": "object", "properties": {}}),
            })
        if defs:
            logger.debug(f"[OpenAIResponsesProvider] Initialized {len(defs)} tools")
        return defs

    def _exec_tool(self, name: str, args: Dict):
        """Run an async legacy tool from this sync generator via a background loop."""
        if not hasattr(self, '_bg_loop'):
            self._bg_loop = asyncio.new_event_loop()
            Thread(target=lambda: (asyncio.set_event_loop(self._bg_loop), self._bg_loop.run_forever()), daemon=True).start()
        fut = asyncio.run_coroutine_threadsafe(legacy_tool_registry.execute_tool(name, **args), self._bg_loop)
        return fut.result()

    def _handle_openai_error(self, error: Exception):
        error_code = type(error).__name__
        error_detail = str(error)
        logger.error(f"[OpenAIResponsesProvider] {error_code} - {error_detail}")
        if isinstance(error, openai.RateLimitError):
            message = "Rate limit exceeded. Please try again later."
        elif isinstance(error, openai.AuthenticationError):
            message = "Authentication failed. Please check the Bedrock API key."
        elif isinstance(error, openai.BadRequestError):
            message = "Invalid request format. Please try again with different input."
        elif isinstance(error, openai.APITimeoutError):
            message = "The request timed out. Please try again."
        elif isinstance(error, openai.APIConnectionError):
            message = "Failed to connect to the API. Please check your network."
        else:
            message = "An unexpected error occurred. Please try again."
        raise LLMProviderError(error_code, message, error_detail)

    def _convert_messages(self, messages: List[LLMMessage], system_prompt: Optional[str] = None) -> List[Dict]:
        """Flatten messages to the Responses API input array (role + text content)."""
        out: List[Dict] = []
        if system_prompt:
            out.append({"role": "system", "content": system_prompt})
        for msg in messages:
            content = msg.content
            if isinstance(content, dict):
                content = content.get("text", "")
            ctx = getattr(msg, 'context', None)
            if ctx and isinstance(ctx, dict):
                items = [f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in ctx.items() if v is not None]
                if items:
                    content = f"Context Information:\n{' | '.join(items)}\n{content}"
            out.append({"role": msg.role, "content": str(content)})
        return out

    def generate_content(self, messages: List[LLMMessage], system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        text_parts: List[str] = []
        for chunk in self.generate_stream(messages, system_prompt, **kwargs):
            if t := chunk.get('content', {}).get('text'):
                text_parts.append(t)
        return LLMResponse(content={"text": "".join(text_parts)}, metadata={'model': self.model_id})

    def generate_stream(self, messages: List[LLMMessage], system_prompt: Optional[str] = None, **kwargs) -> Iterator[Dict]:
        try:
            mt = kwargs.get('max_tokens', self.llm_params.max_tokens)
            # Reasoning effort (Responses: low/medium/high/xhigh; clamp our 'max').
            intent = self.llm_params.thinking or {}
            reasoning_on = bool(intent.get("enabled", True)) if intent else False
            # max_output_tokens counts reasoning tokens too; with reasoning + a multi-round
            # tool loop a small cap gets eaten before the final answer, yielding empty output.
            # 16k (the Strands chain's floor) still ran dry across tool rounds in testing; 32k
            # was the smallest floor that reliably left budget for the final answer.
            req: Dict = {
                "model": self.model_id,
                "input": self._convert_messages(messages, system_prompt),
                "max_output_tokens": max(mt or 0, 32000) if reasoning_on else mt,
                "stream": True,
            }
            if reasoning_on:
                effort = intent.get("effort") or "high"
                req["reasoning"] = {"effort": "xhigh" if effort == "max" else effort}
            if self._tool_defs:
                req["tools"] = self._tool_defs

            for _ in range(_MAX_TOOL_ROUNDS):
                calls: List[Dict] = []  # {name, call_id, arguments}
                output_items = []       # full output of this round (incl. reasoning items)
                # A round that calls a tool may ALSO emit assistant text (a pre-answer before the tool result); streaming it then looping would duplicate the reply. 
                # The function_call item.added precedes the text deltas, so once we've seen one we suppress this round's text — the real answer comes after tool results.
                saw_tool = False
                thinking_shown = False
                for ev in self.client.responses.create(**req):  # type: ignore[arg-type]
                    t = ev.type
                    item_type = getattr(getattr(ev, 'item', None), 'type', None)
                    if t == 'response.output_item.added' and item_type == 'function_call':
                        saw_tool = True
                        yield {'tool_use': {'toolUseId': ev.item.call_id, 'name': ev.item.name}}
                    elif t == 'response.output_item.added' and item_type == 'reasoning' and not thinking_shown:
                        # Grok/GPT-5 on Mantle don't stream readable reasoning text, only a
                        # reasoning item marker. Surface a placeholder so the UI shows the model
                        # is thinking, consistent with Claude's streamed reasoning.
                        thinking_shown = True
                        yield {'thinking': {'text': 'Thinking…'}}
                    elif t == 'response.output_text.delta' and ev.delta and not saw_tool:
                        yield {'content': {'text': ev.delta}}
                    elif t in ('response.reasoning_text.delta', 'response.reasoning_summary_text.delta') and getattr(ev, 'delta', None):
                        yield {'thinking': {'text': ev.delta}}
                    elif t == 'response.completed':
                        output_items = [o.model_dump() for o in ev.response.output]
                        calls = [o for o in output_items if o.get('type') == 'function_call']

                if not calls:  # no tool use → final answer already streamed
                    yield {'metadata': {'stop_reason': 'stop'}}
                    return

                # Reasoning models need the prior output items (reasoning + function_call)
                # passed back alongside the tool outputs — append the whole round, then results.
                req["input"].extend(output_items)
                for c in calls:
                    args = json.loads(c['arguments']) if c['arguments'] else {}
                    try:
                        result = self._exec_tool(c['name'], args)
                        output = json.dumps(result) if not isinstance(result, str) else result
                    except Exception as e:
                        output = json.dumps({"error": str(e)})
                    req["input"].append({"type": "function_call_output", "call_id": c['call_id'], "output": output})

            yield {'metadata': {'stop_reason': 'max_tool_rounds'}}
        except Exception as e:
            self._handle_openai_error(e)

    def multi_turn_generate(self, message: LLMMessage, history: Optional[List[LLMMessage]] = None,
                            system_prompt: Optional[str] = None, **kwargs) -> Iterator[Dict]:
        try:
            messages = list(history or [])
            messages.append(message)
            yield from self.generate_stream(messages, system_prompt, **kwargs)
        except Exception as e:
            self._handle_openai_error(e)
