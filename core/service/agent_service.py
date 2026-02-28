# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, AsyncIterator, Any, List, Optional, Union, TYPE_CHECKING, cast
from core.service import BaseService
from core.session.models import Session
from core.config import env_config
from genai.agents.provider import AgentProvider
from . import logger

if TYPE_CHECKING:
    from genai.agents.agentcore_client import AgentCoreClient


class AgentService(BaseService):
    """Strands Agent service implementation with streaming capabilities.

    Supports two execution modes:
    - Local mode: Uses AgentProvider to run agent locally
    - Remote mode: Uses AgentCoreClient to call AgentCore Runtime

    Mode is controlled by USE_AGENTCORE environment variable.
    """

    def __init__(self, module_name: str):
        """Initialize Agent service

        Args:
            module_name: Name of the module using this service
        """
        super().__init__(module_name)
        self._agent_providers: Dict[str, AgentProvider] = {}
        self._agentcore_client = None

        # Check if AgentCore mode is enabled
        self._use_agentcore = env_config.agentcore_config.get('enabled', False)
        if self._use_agentcore:
            logger.info(f"[AgentService] AgentCore mode enabled for module: {module_name}")
    
    def _convert_to_strands_format(self, ui_history: List[Dict]) -> List:
        """Convert UI history messages to Strands Message format
        
        Args:
            ui_history: List of message dicts with 'role' and 'content' keys from UI
            
        Returns:
            List of Strands Message objects
        """
        if not ui_history:
            return []
            
        try:
            from strands.types.content import Message
            strands_messages = []
            
            for msg in ui_history:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    # Handle different content formats
                    content = msg['content']
                    if isinstance(content, dict):
                        # Extract text from dict format
                        content = content.get('text', str(content))
                    elif isinstance(content, (list, tuple)):
                        # Convert list/tuple to text
                        content = ' '.join(str(item) for item in content)
                    
                    # Convert to correct Bedrock format
                    strands_msg = Message({
                        'role': msg['role'],
                        'content': [
                            {
                                'text': str(content)
                            }
                        ]
                    })
                    strands_messages.append(strands_msg)
                    
            logger.debug(f"[AgentService] Converted {len(ui_history)} UI messages to Strands format")
            return strands_messages
            
        except Exception as e:
            logger.error(f"[AgentService] Error converting UI messages to Strands format: {str(e)}")
            return []
    
    def _get_agentcore_client(self):
        """Get or initialize AgentCoreClient for remote execution.

        Returns:
            AgentCoreClient instance
        """
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
            logger.info(f"[AgentService] Initialized AgentCoreClient: {runtime_arn}")

        return self._agentcore_client

    async def _get_agent_provider(
        self, model_id: str, system_prompt: str
    ) -> Union[AgentProvider, "AgentCoreClient"]:
        """Get agent provider (local or remote based on config).

        Args:
            model_id: ID of the model to get provider for
            system_prompt: System prompt for the agent

        Returns:
            AgentProvider (local) or AgentCoreClient (remote)
        """
        # Use AgentCore client if enabled
        if self._use_agentcore:
            return self._get_agentcore_client()

        # Use cached local provider if available
        if model_id in self._agent_providers:
            logger.debug(f"[AgentService] Using cached provider for model {model_id}")
            return self._agent_providers[model_id]

        try:
            # Create local provider
            provider = AgentProvider(
                model_id=model_id,
                system_prompt=system_prompt
            )
            logger.info(f"[AgentService] Initialized AgentProvider with model {model_id}")
            # Cache provider
            self._agent_providers[model_id] = provider

            return provider

        except Exception as e:
            logger.error(f"[AgentService] Failed to initialize AgentProvider: {str(e)}")
            raise

    def _get_default_tool_config(self) -> Dict[str, Any]:
        """Get default tool configuration for the service
        
        Note: No longer reads from database - modules should pass their own legacy_tools
        
        Returns:
            Default tool configuration dictionary
        """
        tool_config = {
            'enabled': True,
            'legacy_tools': [],  # Empty by default - modules should specify their tools
            'mcp_tools_enabled': False,  # Default disable MCP for performance
            'strands_tools_enabled': True,
        }
        
        logger.debug("[AgentService] Using default tool config (no legacy tools)")
        return tool_config

    async def _generate_stream_async(
        self,
        session: Session,
        prompt: str,
        system_prompt: str,
        history: Optional[List[Dict]] = None,
        tool_config: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[Dict]:
        """Internal method for streaming generation with common logic.

        Supports both local (AgentProvider) and remote (AgentCoreClient) execution.

        Args:
            session: User session
            prompt: Current user prompt
            system_prompt: System prompt for the agent
            history: Optional list of previous messages in UI format
            tool_config: Optional tool configuration override

        Returns:
            AsyncIterator yielding standardized agent response dictionaries
        """
        if not prompt:
            yield {"text": "Please provide a user prompt."}
            return

        try:
            # Get model_id with fallback to module default
            model_id = await self.get_session_model(session)

            # Get provider instance (local or remote)
            provider = await self._get_agent_provider(model_id, system_prompt)

            # Use provided tool config or get default
            if tool_config is None:
                tool_config = self._get_default_tool_config()
            else:
                logger.debug(f"Using provided tool config: {tool_config}")

            # Handle differently based on provider type
            if self._use_agentcore:
                # AgentCoreClient: pass model_id and system_prompt, history in UI format
                client = cast("AgentCoreClient", provider)
                async for chunk in client.generate_stream(
                    prompt=prompt,
                    history_messages=history,  # AgentCore handles conversion
                    tool_config=tool_config,
                    model_id=model_id,
                    system_prompt=system_prompt
                ):
                    if not isinstance(chunk, dict):
                        logger.warning(f"Unexpected chunk type: {type(chunk)}")
                        continue
                    yield chunk
            else:
                # Local AgentProvider: convert history to Strands format
                strands_history = None
                if history:
                    strands_history = self._convert_to_strands_format(history)

                async for chunk in provider.generate_stream(prompt, strands_history, tool_config):
                    if not isinstance(chunk, dict):
                        logger.warning(f"Unexpected chunk type: {type(chunk)}")
                        continue
                    yield chunk

        except Exception as e:
            logger.error(f"Error in streaming generation: {str(e)}", exc_info=True)
            yield {"text": f"I apologize, but I encountered an error while processing your request: {str(e)}"}

    async def streaming_reply_with_history(
        self, 
        session: Session, 
        message: str, 
        system_prompt: str, 
        history: List[Dict],
        tool_config: Dict[str, Any],
        persist: bool = False
    ) -> AsyncIterator[Dict]:
        """
        Generate streaming response with conversation history (multi-turn)
        
        Args:
            session: User session
            message: Current user message
            system_prompt: System prompt for the agent
            history: List of previous messages in UI format
            tool_config: Optional tool configuration override
            persist: If True, save conversation to DynamoDB after response completes
            
        Returns:
            AsyncIterator yielding standardized agent response dictionaries
        """
        accumulated_text = []
        try:
            async for chunk in self._generate_stream_async(
                session=session,
                prompt=message,
                system_prompt=system_prompt,
                history=history,
                tool_config=tool_config
            ):
                if text := chunk.get('text'):
                    accumulated_text.append(text)
                yield chunk

            if persist and accumulated_text:
                session.history = history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": ''.join(accumulated_text)},
                ]
                await self.session_store.save_session(session)
                logger.debug(f"Auto-saved session {session.session_id} (cloud_sync)")

        except Exception as e:
            logger.error(f"Error in streaming reply with history: {str(e)}", exc_info=True)
            yield {"text": f"I apologize, but I encountered an error while processing your request: {str(e)}"}

    async def gen_text_stream(
        self, 
        session: Session, 
        message: str, 
        system_prompt: str, 
        tool_config: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[Dict]:
        """
        Generate text with streaming response (single-turn)
        
        Args:
            session: User session
            message: The user message
            system_prompt: System prompt for the agent
            tool_config: Optional tool configuration override
            
        Returns:
            AsyncIterator yielding standardized agent response dictionaries
        """
        async for chunk in self._generate_stream_async(
            session=session,
            prompt=message,
            system_prompt=system_prompt,
            history=None,  # No history for single-turn
            tool_config=tool_config
        ):
            yield chunk

    async def clear_history(self, session: Session) -> None:
        """Clear chat history for a session

        Args:
            session: Active chat session to clear history for

        Note:
            - Clears the history list
            - Updates timestamp
            - Persists changes to session store
        """
        session.history = []  # Clear message history
        await self.session_store.save_session(session)
        logger.debug(f"[AgentService] Cleared history for session {session.session_id}")

    def is_agentcore_enabled(self) -> bool:
        """Check if AgentCore remote mode is enabled.

        Returns:
            True if using AgentCore Runtime, False for local execution
        """
        return self._use_agentcore

    async def health_check(self) -> Dict[str, Any]:
        """Check agent service health.

        Returns:
            Health status dict with mode and status
        """
        result: Dict[str, Any] = {
            "mode": "agentcore" if self._use_agentcore else "local",
            "module": self.module_name
        }

        if self._use_agentcore:
            try:
                client = self._get_agentcore_client()
                health = await client.health_check()
                result["status"] = health.get("status", "unknown")
                result["agentcore"] = health
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
        else:
            result["status"] = "healthy"

        return result
