import asyncio
import gradio as gr
from typing import List, Dict, AsyncGenerator, Union, Optional, Tuple
from core.logger import logger
from genai.models.model_manager import model_manager
from modules import BaseHandler
from core.service.agent_service import AgentService
from .prompts import ASSISTANT_PROMPT


class AssistantHandlers(BaseHandler[AgentService]):
    """Handlers with Agent capabilities for advanced tool use and reasoning."""
    
    # Module name for the handler
    _module_name: str = "assistant"

    # Maximum number of messages to show in UI    
    _max_display_messages: int = 24

    @classmethod
    def get_user_name(cls, request: gr.Request) -> Optional[str]:
        """Get authenticated user from FastAPI request."""
        if user_name := request.session.get('auth_user', {}).get('username'):
            return user_name
        else:
            logger.warning("[AssistantHandlers] No authenticated user found")
            return None

    @classmethod
    def get_available_models(cls) -> List[Tuple[str, str]]:
        """Get list of available models with tool use capabilities."""
        try:
            # Filter for models with tool use capabilities
            if models := model_manager.get_models(filter={'tool_use': True}):
                logger.debug(f"[AssistantHandlers] Get {len(models)} available models with tool use")
                return [(f"{m.name}, {m.api_provider}", m.model_id) for m in models]
            else:
                logger.warning("[AssistantHandlers] No matching models found.")
                return []

        except Exception as e:
            logger.error(f"[AssistantHandlers] Failed to fetch models: {e}", exc_info=True)
            return []

    @classmethod
    async def load_history_options(
        cls, request: gr.Request
    ) -> Tuple[List[Dict[str, str]], Optional[str]]:
        """
        Load chat history and configuration for current user.

        Args:
            request: Gradio request with session data

        Returns:
            Tuple containing:
            - List of message dictionaries for gr.Chatbot UI
            - Selected model_id for the dropdown
        """
        try:
            # Initialize session
            service, session = await cls._init_session(request)

            # Load history from session (AgentService inherits from BaseService)
            history_future = service.load_session_history(
                session=session,
                max_messages=cls._max_display_messages
            )
            model_future = service.get_session_model(session)
            
            latest_history, model_id = await asyncio.gather(
                history_future, model_future
            )

            return latest_history, model_id

        except Exception as e:
            logger.error(f"[AssistantHandlers] Failed to load history: {e}", exc_info=True)
            return [], None

    @classmethod
    async def clear_chat_history(
        cls, request: gr.Request
    ) -> None:
        """Clear chat history when clear button is clicked."""
        try:
            # Initialize session
            service, session = await cls._init_session(request)

            # Clear history in session
            await service.clear_history(session)
            logger.debug(f"[AssistantHandlers] Cleared history for user: {session.user_name}")
            gr.Info(f"Cleared history for session {session.session_name}", duration=3)
            
        except Exception as e:
            logger.error(f"[AssistantHandlers] Failed to clear history: {e}", exc_info=True)

    @classmethod
    async def undo_last_message(
        cls, request: gr.Request
    ) -> None:
        """Remove the last pair of messages from chat history."""
        try:
            # Initialize session
            service, session = await cls._init_session(request)

            # Check if there are messages to remove
            if len(session.history) >= 2:
                # Remove the last two messages (assistant and user)
                session.history = session.history[:-2]
                # Update session in database
                await service.session_store.save_session(session)
                logger.debug(f"[AssistantHandlers] Removed last message pair for user: {session.user_name}")
            else:
                # No messages to remove
                gr.Info(f"No messages to undo for this session.", duration=3)
            
        except Exception as e:
            logger.error(f"[AssistantHandlers] Failed to undo last message: {e}", exc_info=True)

    @classmethod
    async def send_message(
        cls,
        ui_input: Union[str, Dict],
        ui_history: List[Dict[str, str]],
        model_id: str,
        request: gr.Request
    ) -> AsyncGenerator[List[gr.ChatMessage], None]:
        """Stream assistant's response to Chatbot

                Args:
            ui_input: Raw input from Gradio (text string or dict with text/files)
            ui_history: Current chat history (managed by Gradio)
            model_id: Selected model identifier
            request: Gradio request with session data

        Yields:
            ChatMessage status and content messages
        """

        info_msg = gr.ChatMessage(
            role="assistant",
            content='',
            metadata={'title':'ℹ️ '}
        )

        # Input validation
        if not model_id:
            info_msg.content="Please select a model for Assistant module."
            yield [info_msg]
            return

        try:
            # Convert Gradio input to a unified dictionary format
            unified_input = cls._normalize_input(ui_input)
            if not unified_input:
                info_msg.content="Please provide a message or file."
                return

            service, session = await cls._init_session(request)
            
            tool_config = {
                'enabled': True, 
                'include_legacy': True, 
                'include_mcp': False,  # Default disable MCP for performance
                'include_strands': True, 
                'tool_filter': None
            }

            # Configuration constants
            USER_CONTENT_FILES = ['image', 'audio', 'video', 'document']
            
            accumulated_content = ""
            messages = []

            async for chunk in service.streaming_reply_with_history(
                session=session,
                prompt=unified_input.get('text', ''),
                system_prompt=ASSISTANT_PROMPT,
                history=ui_history,
                tool_config=tool_config
            ):
                # Handle main content
                if text := chunk.get('text', ''):
                    accumulated_content += text
                    
                # Handle thinking - keep all thinking messages
                if thinking := chunk.get('thinking', ''):
                    thinking_msg = gr.ChatMessage(
                        role="assistant",
                        content=f"💭 {thinking}",
                        metadata={"title": "🤔 思考过程", "status": "pending"}
                    )

                    messages.append(thinking_msg)
                    yield messages
                    
                # Handle tool use - simplified logic
                if tool_use := chunk.get('tool_use'):
                    tool_name = tool_use.get('name', 'unknown')
                    tool_status = tool_use.get('status', 'running')
                    tool_params = tool_use.get('params', {})
                    tool_result = tool_use.get('result', '')
                    
                    # Configuration constants
                    TOOL_RESULT_MAX_LENGTH = 200
                    TOOL_PARAM_MAX_LENGTH = 100
                    
                    # Truncate parameter display
                    params_str = str(tool_params)
                    if len(params_str) > TOOL_PARAM_MAX_LENGTH:
                        params_str = params_str[:TOOL_PARAM_MAX_LENGTH] + "..."
                    
                    # Build status message content based on status
                    if tool_status == 'running':
                        tool_content = f"🔧 正在调用工具: **{tool_name}**\n参数: `{params_str}`"
                        title = f"🔧 工具调用: {tool_name}"
                        status = "pending"
                        
                    elif tool_status in ['completed', 'success']:
                        tool_content = f"✅ 工具执行完成: **{tool_name}**\n参数: `{params_str}`"
                        if tool_result:
                            result_preview = str(tool_result)[:TOOL_RESULT_MAX_LENGTH]
                            if len(str(tool_result)) > TOOL_RESULT_MAX_LENGTH:
                                result_preview += "..."
                            tool_content += f"\n结果: {result_preview}"
                        title = f"✅ 工具完成: {tool_name}"
                        status = "done"
                        
                    elif tool_status == 'failed':
                        tool_content = f"❌ 工具执行失败: **{tool_name}**\n参数: `{params_str}`"
                        if tool_result:
                            error_preview = str(tool_result)[:TOOL_RESULT_MAX_LENGTH]
                            if len(str(tool_result)) > TOOL_RESULT_MAX_LENGTH:
                                error_preview += "..."
                            tool_content += f"\n错误: {error_preview}"
                        title = f"❌ 工具错误: {tool_name}"
                        status = "done"
                    else:
                        # Unknown status, skip
                        continue
                    
                    # Create tool status message
                    tool_msg = gr.ChatMessage(
                        role="assistant",
                        content=tool_content,
                        metadata={"title": title, "status": status}
                    )
                    
                    # For completed/failed status, remove previous pending messages for the same tool
                    if status == "done":
                        messages = [m for m in messages if not (
                            m.role == "assistant" and 
                            m.metadata and 
                            m.metadata.get("title", "").endswith(f": {tool_name}") and
                            m.metadata.get("status") == "pending"
                        )]
                    
                    messages.append(tool_msg)
                    yield messages
                        
                # Handle files - distinguish between user-needed files and system files
                if files := chunk.get('files', []):
                    for file_info in files:
                        if isinstance(file_info, dict):
                            file_path = file_info.get('path', '')
                            file_type = file_info.get('type', 'file')
                            language = file_info.get('language', '')
                        else:
                            file_path = str(file_info)
                            file_type = 'file'
                            language = ''
                        
                        if file_type in USER_CONTENT_FILES:
                            # User-needed files -> add to content message, use Gradio components
                            if file_type == 'image':
                                # Create message containing image
                                image_msg = gr.ChatMessage(
                                    role="assistant",
                                    content=gr.Image(value=file_path, label="Generated Image")
                                )
                                messages.append(image_msg)
                                yield messages
                            elif file_type == 'audio':
                                audio_msg = gr.ChatMessage(
                                    role="assistant", 
                                    content=gr.Audio(value=file_path, label="Generated Audio")
                                )
                                messages.append(audio_msg)
                                yield messages
                            elif file_type == 'video':
                                video_msg = gr.ChatMessage(
                                    role="assistant",
                                    content=gr.Video(value=file_path, label="Generated Video")
                                )
                                messages.append(video_msg)
                                yield messages
                            elif file_type == 'document':
                                # Document type still uses text link
                                accumulated_content += f"\n\n📄 生成文档: [{file_path}]({file_path})"
                                content_updated = True
                        else:
                            # System files -> display as status message
                            file_content = f"📎 生成文件: `{file_path}`"
                            if language:
                                file_content += f" ({language})"
                            
                            file_msg = gr.ChatMessage(
                                role="assistant",
                                content=file_content,
                                metadata={"title": f"📎 文件生成: {file_type}", "status": "done"}
                            )
                            messages.append(file_msg)  # Add directly, don't replace
                            yield messages

                # Update content message
                if accumulated_content:
                    # Remove previous content message
                    content_msgs = [m for m in messages if m.role == "assistant" and not m.metadata]
                    if content_msgs:
                        messages.remove(content_msgs[-1])
                    
                    messages.append(gr.ChatMessage(role="assistant", content=accumulated_content))
                    yield messages

                await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"[AssistantHandlers] Error: {e}", exc_info=True)
            error_msg = gr.ChatMessage(
                role="assistant", 
                content="I encountered an error. Please try again.",
                metadata={"title": "❌ Error"}
            )
            yield messages + [error_msg] if 'messages' in locals() else [error_msg]
