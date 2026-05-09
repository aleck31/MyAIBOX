# Copyright iX.
# SPDX-License-Identifier: MIT-0
import time
import weakref
from typing import Dict, AsyncIterator, Any, List, Optional
from backend.core.service import BaseService
from backend.core.session.models import Session
from backend.genai.agents.provider import AgentProvider
from . import logger

# Agent cache limits
_AGENT_TTL = 7200   # 2 hours idle eviction
_AGENT_MAX = 100    # Hard cap; LRU evicts oldest when exceeded

# Weak registry of all live AgentService instances — used at shutdown to
# release cached Agents and their MCP subprocesses deterministically.
_instances: "weakref.WeakSet[AgentService]" = weakref.WeakSet()


def shutdown_all() -> None:
    """Destroy every cached AgentProvider across all AgentService instances.
    Call this from the FastAPI lifespan shutdown to avoid orphaned MCP clients."""
    for service in list(_instances):
        for sid, (provider, _) in list(service._agent_cache.items()):
            try:
                provider.destroy()
            except Exception as e:
                logger.warning(f"[AgentService] destroy({sid}) failed: {e}")
        service._agent_cache.clear()


class AgentService(BaseService):
    """Strands Agent service with per-session Agent caching."""

    def __init__(self, module_name: str):
        super().__init__(module_name)
        # Per-session agent cache: {session_id: (AgentProvider, last_used_timestamp)}
        self._agent_cache: Dict[str, tuple[AgentProvider, float]] = {}
        _instances.add(self)

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
        """Cache an AgentProvider for a session. Evicts LRU entry if at capacity."""
        if len(self._agent_cache) >= _AGENT_MAX and session_id not in self._agent_cache:
            # Evict the oldest entry by last-used timestamp
            oldest_sid = min(self._agent_cache, key=lambda s: self._agent_cache[s][1])
            old_provider, _ = self._agent_cache.pop(oldest_sid)
            old_provider.destroy()
            logger.warning(f"[AgentService] Cache full ({_AGENT_MAX}); evicted LRU agent: {oldest_sid}")
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

    async def _get_or_create_provider(
        self,
        session: Session,
        model_id: str,
        system_prompt: str,
        history: Optional[List[Dict]] = None,
        tool_config: Optional[Dict] = None,
        skills: Optional[List] = None,
    ) -> AgentProvider:
        """Get cached provider or create new one with history recovery."""
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
            skills=skills,
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
        skills: Optional[List] = None,
    ) -> AsyncIterator[Dict]:
        """Streaming generation with cached Agent."""
        if not prompt:
            yield {"text": "Please provide a user prompt."}
            return

        try:
            model_id = await self.get_session_model(session)
            provider = await self._get_or_create_provider(
                session, model_id, system_prompt, history, tool_config, skills=skills,
            )

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
        skills: Optional[List] = None,
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
                skills=skills,
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

    async def health_check(self) -> Dict[str, Any]:
        return {
            "module": self.module_name,
            "cached_agents": len(self._agent_cache),
            "status": "healthy",
        }
