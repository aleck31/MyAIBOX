# Copyright iX.
# SPDX-License-Identifier: MIT-0
import gradio as gr
from typing import Dict, Optional
from core.logger import logger
from core.service.gen_service import GenService
from modules import BaseHandler
from .prompts import SYSTEM_PROMPTS, STYLES


# Language options
LANGS = ["en_US", "zh_CN", "zh_TW", "ja_JP", "de_DE", "fr_FR"]
# Text operation definitions with handlers - defined after class
TEXT_OPERATIONS = {
    "Proofreading ✍️": {
        "description": "Check spelling, grammar, and improve clarity",
        "function": lambda text, options, request: TextHandlers.proofread(text, options, request),
        "options": {}
    },
    "Rewrite 🔄": {
        "description": "Rewrite with different style and tone",
        "function": lambda text, options, request: TextHandlers.rewrite(text, options, request),
        "options": {
            "label": "Style",
            "type": "dropdown",
            "choices": list(STYLES.keys()),
            "default": "正常"
        }
    },
    "Reduction ✂️": {
        "description": "Simplify and remove redundant information",
        "function": lambda text, options, request: TextHandlers.reduce(text, options, request),
        "options": {}
    },
    "Expansion 📝": {
        "description": "Add details and background information",
        "function": lambda text, options, request: TextHandlers.expand(text, options, request),
        "options": {}
    }
}

class TextHandlers(BaseHandler[GenService]):
    """Handlers for text processing with style support"""
    
    # Module name for the handler
    _module_name: str = "text"

    @classmethod
    async def _build_content(cls, text: str, operation: str, options: Dict) -> Dict[str, str]:
        """Build content for text processing"""
        target_lang = options.get('target_lang', 'en_US')
        system_prompt = SYSTEM_PROMPTS[operation].format(target_lang=target_lang)
        
        tag = 'original_text'
        if operation == 'rewrite':
            style_key = options.get('style', '正常')
            style_prompt = STYLES[style_key]['prompt']
            user_prompt = f"""Rewrite the text within <{tag}> </{tag}> tags following this style instruction:
                {style_prompt}
                Ensuring the output is in {target_lang} language:
                <{tag}>
                {text}
                </{tag}>
                """
        else:
            user_prompt = f"""Process the text within <{tag}></{tag}> tags according to the given instructions:
            Ensuring the output is in {target_lang} language:
            <{tag}>
            {text}
            </{tag}>
            """
                
        return {
            "text": user_prompt,
            "system_prompt": system_prompt
        }

    @classmethod
    async def handle_request(
        cls,
        text: str,
        operation: str,
        options: Optional[Dict],
        request: gr.Request
    ) -> str:
        """Handle text processing request with authentication"""
        if not text:
            return "Please provide some text to process."

        try:
            # Get services
            service, session = await cls._init_session(request)

            # Build prompt with operation-specific configuration
            options = options or {}
            content = await cls._build_content(text, operation, options)
            logger.debug(f"Build content: {content}")

            # Update session with style-specific system prompt
            session.context['system_prompt'] = content.pop('system_prompt')        
            # Persist updated context to session store
            # await service.session_store.save_session(session)

            # Generate response with session context
            response = await service.gen_text(
                session=session,
                content=content
            )

            if not response:
                raise ValueError("Empty response from service")

            if isinstance(response, dict):
                return response.get('text')
            else:
                # returns the content string directly
                return response

        except Exception as e:
            logger.error(f"[TextHandlers] Failed to generate text: {str(e)}")
            return "An error occurred while processing your text. Please try again."

    @classmethod
    async def proofread(cls, text: str, options: Optional[Dict], request: gr.Request) -> str:
        """Proofread and correct text"""
        return await cls.handle_request(text, 'proofread', options, request)

    @classmethod
    async def rewrite(cls, text: str, options: Optional[Dict], request: gr.Request) -> str:
        """Rewrite text in different style"""
        return await cls.handle_request(text, 'rewrite', options, request)

    @classmethod
    async def reduce(cls, text: str, options: Optional[Dict], request: gr.Request) -> str:
        """Reduce and simplify text"""
        return await cls.handle_request(text, 'reduce', options, request)

    @classmethod
    async def expand(cls, text: str, options: Optional[Dict], request: gr.Request) -> str:
        """Expand text with more details"""
        return await cls.handle_request(text, 'expand', options, request)

    @classmethod
    async def process_text(cls, operation: str, text: str, request: gr.Request, *args) -> str:
        """Process text based on selected operation with proper error handling
        
        Args:
            operation: Selected text operation
            text: Input text to process
            request: Gradio request object containing session data
            *args: Additional arguments (style options and target language)
        """
        try:
            # First argument is target_lang after operation and text
            target_lang = args[0]
            # Other args are after target_lang
            other_args = args[1:]
            
            # Collect options for the current operation
            options = {"target_lang": target_lang}
            
            # Get operation info
            op_info = TEXT_OPERATIONS[operation]
            
            if op_info["options"]:
                opt = op_info["options"]
                # Find the corresponding argument that matches this option
                for arg in other_args:
                    if arg is not None:  # Only use non-None arguments
                        options[opt['label'].lower()] = arg
                        break
            
            # Call appropriate handler function
            result = await op_info["function"](text, options, request)
            return result
            
        except Exception as e:
            logger.error(f"Error in process_text: {str(e)}")
            return "An error occurred while processing your text. Please try again."
