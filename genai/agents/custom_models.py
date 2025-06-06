# Copyright iX.
# SPDX-License-Identifier: MIT-0
from typing import Dict, List, Optional, Any, AsyncGenerator
from core.logger import logger
from core.config import env_config
from utils.aws import get_secret
from strands import Agent
from strands.tools.mcp import MCPClient
from strands.types.models import Model
from mcp.client.streamable_http import streamablehttp_client
from genai.tools.tool_manager import tool_manager
from genai.models import LLMResponse
from genai.models.api_providers.google_gemini import GeminiProvider


class GeminiModel(Model):
    """Gemini provider implementation for Strands Agents integration"""
    #Todo: Implement a Gemini provider following Strands Agent custom model provider guide
    #Guide link: https://strandsagents.com/latest/user-guide/concepts/model-providers/custom_model_provider/
    pass
