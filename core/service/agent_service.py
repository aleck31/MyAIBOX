# Copyright iX.
# SPDX-License-Identifier: MIT-0
import time
from typing import Dict, AsyncIterator, Any, List, Optional, Union, TYPE_CHECKING, cast
from core.service import BaseService
from core.session.models import Session
from core.config import env_config
from genai.agents.provider import AgentProvider
from . import logger

if TYPE_CHECKING:
    from genai.agents.agentcore_client import AgentCoreClient

# Agent cache TTL: 2 hours
_AGENT_TTL = 7200


class AgentService(BaseService):
    """Strands Agent service with per-session Agent caching.

    Supports two execution modes:
    - Local mode: Uses AgentProvider with cached Agent instances
    - Remote mode: Uses AgentCoreClient to call AgentCore Runtime
    """

    def __init__(self, module_name: str):
        super().__init__(module_name)
        # Per-session agent cache: {session_id: (AgentProvider, last_used_timestamp)}
        self._agent_cache: Dict[str, tuple[AgentProvider, float]] = {}
        self._agentcore_client = None
        self._use_agentcore = env_config.agentcore_config.get('enabled', False)
        if self._use_agentcore:
            logger.info(f"[AgentService] AgentCore mode enabled for module: {module_name}")

    def _evict_expired(self):
        """Remove expired Agent instances."""
        now = time.time()
        expired = [sid for sid, (_, ts) in self._agent_cache.items() if now - ts > _AGENT_TTL]
        for sid in expired:
            provider, _ = self._agent_cache.pop(sid)
            provider.destroy()
            logger.info(f"[AgentService] Evicted expired agent: {sid}")

    def _get_cached_provider(self, session_id: str) -> Optional[AgentProvider]:
        """Get cached AgentProvider if exists and not expired."""
        self._evict_expired()
        if entry := self._agent_cache.get(session_id):
            provider, _ = entry
            self._agent_cache[session_id] = (provider, time.time())
            return provider
        return None

    def _cache_provider(self, session_id: str, provider: AgentProvider):
        """Cache an AgentProvider for a session."""
        self._agent_cache[session_id] = (provider, time.time())

    def _remove_cached_provider(self, session_id: str):
        """Remove and destroy cached AgentProvider."""
        if entry := self._agent_cache.pop(session_id, None):
            entry[0].destroy()

    def _convert_to_strands_format(self, ui_history: List[Dict]) -> List:
        """Convert UI history messages to Strands Message format"""
        if not ui_history:
            return []

        try:
            from strands.types.content import Message
            strands_messages = []

            for msg in ui_history:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    content = msg['content']
                    if isinstance(content, dict):
                        content = content.get('text', str(content))
                    elif isinstance(content, (list, tuple)):
                        content = ' '.join(str(item) for item in content)

                    strands_messages.append(Message({
                        'role': msg['role'],
                        'content': [{'text': str(content)}]
                    }))

            return strands_messages

        except Exception as e:
            logger.error(f"[AgentService] Error converting messages: {e}")
            return []

    def _get_agentcore_client(self):
        """Get or initialize AgentCoreClient for remote execution."""
        if self._agentcore_client is None:
            from genai.agents.agentcore_client import AgentCoreClient
            config = env_config.agentcore_config
            runtime_arn = config.get('runtime_arn')
            if not runtime_arn:
                raise ValueError("AGENTCORE_RUNTIME_ARN not configured")
            self._agentcore_client = AgentCoreClient(
                runtime_arn=runtime_arn,
                region=config.get('region'),
                endpoint_name=config.get('endpoint_name', 'DEFAULT')
            )
        return self._agentcore_client

    async def _get_or_create_provider(
        self,
        session: Session,
        model_id: str,
        system_prompt: str,
        history: Optional[List[Dict]] = None,
        tool_config: Optional[Dict] = None,
    ) -> Union[AgentProvider, "AgentCoreClient"]:
        """Get cached provider or create new one with history recovery."""
        if self._use_agentcore:
            return self._get_agentcore_client()

        session_id = session.session_id

        # Return cached provider if available
        if provider := self._get_cached_provider(session_id):
            # Update model if changed
            if provider.model_id != model_id:
                provider.update_model(model_id)
            return provider

        # No cache — recover history: frontend first, then DynamoDB
        strands_history = None
        if history:
            strands_history = self._convert_to_strands_format(history)
            logger.debug(f"[AgentService] Recovering {len(history)} messages from frontend")
        else:
            db_history = await self.load_session_history(session)
            if db_history:
                strands_history = self._convert_to_strands_format(db_history)
                logger.debug(f"[AgentService] Recovering {len(db_history)} messages from DynamoDB")

        # Create new provider with recovered history
        provider = AgentProvider(
            model_id=model_id,
            system_prompt=system_prompt,
            tool_config=tool_config or self._get_default_tool_config(),
        )
        # Trigger agent creation with history
        provider._ensure_agent(strands_history)
        self._cache_provider(session_id, provider)
        return provider

    def _get_default_tool_config(self) -> Dict[str, Any]:
        """Get default tool configuration."""
        return {
            'enabled': True,
            'legacy_tools': [],
            'mcp_tools_enabled': False,
            'strands_tools_enabled': True,
        }

    @staticmethod
    def _build_multimodal_prompt(text: str, files: Optional[List[str]] = None):
        """Build Strands-compatible prompt with optional image attachments."""
        if not files:
            return text

        import mimetypes
        content_blocks = []
        if text:
            content_blocks.append({"text": text})

        for file_path in files:
            try:
                mime = mimetypes.guess_type(file_path)[0] or ""
                if not mime.startswith("image/"):
                    continue
                fmt = mime.split("/")[-1]
                if fmt == "jpg":
                    fmt = "jpeg"
                with open(file_path, "rb") as f:
                    content_blocks.append({
                        "image": {"format": fmt, "source": {"bytes": f.read()}}
                    })
            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}")

        return content_blocks if len(content_blocks) > 1 else text

    async def _generate_stream_async(
        self,
        session: Session,
        prompt: str,
        system_prompt: str,
        history: Optional[List[Dict]] = None,
        tool_config: Optional[Dict[str, Any]] = None,
        files: Optional[List[str]] = None,
    ) -> AsyncIterator[Dict]:
        """Streaming generation with cached Agent."""
        if not prompt:
            yield {"text": "Please provide a user prompt."}
            return

        try:
            model_id = await self.get_session_model(session)
            provider = await self._get_or_create_provider(
                session, model_id, system_prompt, history, tool_config
            )

            if self._use_agentcore:
                client = cast("AgentCoreClient", provider)
                async for chunk in client.generate_stream(
                    prompt=prompt,
                    history_messages=history,
                    tool_config=tool_config,
                    model_id=model_id,
                    system_prompt=system_prompt
                ):
                    if isinstance(chunk, dict):
                        yield chunk
            else:
                # Build multimodal prompt if files present
                agent_prompt = self._build_multimodal_prompt(prompt, files)
                async for chunk in provider.generate_stream(agent_prompt):
                    if isinstance(chunk, dict):
                        yield chunk

        except Exception as e:
            logger.error(f"Error in streaming generation: {e}", exc_info=True)
            yield {"text": f"I apologize, but I encountered an error: {str(e)}"}

    async def streaming_reply_with_history(
        self,
        session: Session,
        message: str,
        system_prompt: str,
        history: List[Dict],
        tool_config: Dict[str, Any],
        persist: bool = False,
        files: Optional[List[str]] = None,
    ) -> AsyncIterator[Dict]:
        """Generate streaming response with conversation history."""
        accumulated_text = []
        try:
            async for chunk in self._generate_stream_async(
                session=session,
                prompt=message,
                system_prompt=system_prompt,
                history=history,
                tool_config=tool_config,
                files=files,
            ):
                if text := chunk.get('text'):
                    accumulated_text.append(text)
                yield chunk

            # Cloud sync: write back to DynamoDB after each turn
            if persist and accumulated_text:
                # Get messages from cached agent (most accurate)
                provider = self._get_cached_provider(session.session_id)
                if provider and provider.messages:
                    # Convert Strands messages back to UI format for DynamoDB
                    session.history = self._strands_to_ui_history(provider.messages)
                else:
                    # Fallback: append to provided history
                    session.history = history + [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": ''.join(accumulated_text)},
                    ]
                await self.session_store.save_session(session)
                logger.debug(f"[AgentService] Cloud synced session {session.session_id}")

        except Exception as e:
            logger.error(f"Error in streaming reply: {e}", exc_info=True)
            yield {"text": f"I apologize, but I encountered an error: {str(e)}"}

    def _strands_to_ui_history(self, messages: List) -> List[Dict]:
        """Convert Strands messages back to simple UI format for DynamoDB storage."""
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get('role', '')
                content = msg.get('content', '')
            else:
                role = getattr(msg, 'role', '')
                content = getattr(msg, 'content', '')

            if role not in ('user', 'assistant'):
                continue

            # Extract text from content blocks
            if isinstance(content, list):
                texts = []
                for block in content:
                    if isinstance(block, dict) and 'text' in block:
                        texts.append(block['text'])
                text = '\n'.join(texts)
            elif isinstance(content, str):
                text = content
            else:
                continue

            if text:
                result.append({"role": role, "content": text})
        return result

    async def gen_text_stream(
        self,
        session: Session,
        message: str,
        system_prompt: str,
        tool_config: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[Dict]:
        """Generate text with streaming response (single-turn)."""
        async for chunk in self._generate_stream_async(
            session=session,
            prompt=message,
            system_prompt=system_prompt,
            history=None,
            tool_config=tool_config
        ):
            yield chunk

    async def clear_history(self, session: Session) -> None:
        """Clear chat history — destroy cached Agent and clear DynamoDB."""
        self._remove_cached_provider(session.session_id)
        session.history = []
        await self.session_store.save_session(session)
        logger.debug(f"[AgentService] Cleared history for session {session.session_id}")

    def is_agentcore_enabled(self) -> bool:
        return self._use_agentcore

    async def health_check(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "mode": "agentcore" if self._use_agentcore else "local",
            "module": self.module_name,
            "cached_agents": len(self._agent_cache),
        }
        if self._use_agentcore:
            try:
                client = self._get_agentcore_client()
                health = await client.health_check()
                result["status"] = health.get("status", "unknown")
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
        else:
            result["status"] = "healthy"
        return result
