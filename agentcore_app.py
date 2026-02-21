# Copyright iX.
# SPDX-License-Identifier: MIT-0
"""
AgentCore Runtime entry point for MyAIBOX Agent Service.

This module provides a serverless deployment option for the AI Agent functionality
using AWS Bedrock AgentCore Runtime. It wraps the existing AgentProvider to enable:
- Serverless deployment with up to 8 hours execution time
- Automatic scaling and session isolation
- Integration with AgentCore Memory, Gateway, and Observability
- Streaming responses via Server-Sent Events (SSE)

Usage:
    Local testing:
        python agentcore_app.py

    Deploy to AgentCore:
        agentcore configure -e agentcore_app.py
        agentcore launch

    Invoke (non-streaming):
        agentcore invoke '{"prompt": "Hello"}'

    Invoke (streaming):
        agentcore invoke '{"prompt": "Hello", "stream": true}'
"""
import asyncio
import json
from typing import Dict, Any, Optional, List, AsyncGenerator

from bedrock_agentcore import BedrockAgentCoreApp

from genai.agents.provider import AgentProvider
from genai.models.model_manager import model_manager
from common.logger import logger


# Initialize AgentCore application
app = BedrockAgentCoreApp()


def get_default_model_id() -> str:
    """Get default model ID from configured models"""
    try:
        models = model_manager.get_models()
        # Find first text model with tool_use AND streaming capability
        for model in models:
            if (model.category == 'text' and
                model.capabilities.tool_use and
                model.capabilities.streaming):
                logger.info(f"Selected default model: {model.model_id}")
                return model.model_id
        # Fallback to first available model with tool_use
        for model in models:
            if model.capabilities.tool_use:
                logger.info(f"Selected fallback model: {model.model_id}")
                return model.model_id
    except Exception as e:
        logger.warning(f"Failed to get default model: {e}")

    # Hardcoded fallback - Claude supports both tools and streaming
    return "global.anthropic.claude-sonnet-4-6"


def get_default_tool_config() -> Dict[str, Any]:
    """Get default tool configuration"""
    return {
        'enabled': True,
        'legacy_tools': ['get_weather', 'search_internet'],
        'mcp_tools_enabled': False,
        'strands_tools_enabled': True,
    }


async def stream_agent_async(
    prompt: str,
    model_id: Optional[str] = None,
    system_prompt: str = "You are a helpful AI assistant.",
    history: Optional[List[Dict]] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream agent responses as async generator.

    Args:
        prompt: User input prompt
        model_id: LLM model ID (optional, uses default if not provided)
        system_prompt: System prompt for the agent
        history: Conversation history in Strands format
        tool_config: Tool configuration

    Yields:
        Response chunks with 'text', 'tool_use', 'thinking', 'metadata', etc.
    """
    model_id = model_id or get_default_model_id()
    tool_config = tool_config or get_default_tool_config()

    logger.info(f"Streaming agent with model: {model_id}, prompt length: {len(prompt)}")

    provider = AgentProvider(
        model_id=model_id,
        system_prompt=system_prompt
    )

    try:
        async for chunk in provider.generate_stream(
            prompt=prompt,
            history_messages=history,
            tool_config=tool_config
        ):
            # Yield each chunk as-is for streaming
            yield chunk

        # Final chunk to indicate completion
        yield {'status': 'complete', 'event': 'done'}

    except Exception as e:
        logger.error(f"Agent streaming error: {e}", exc_info=True)
        yield {
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__
        }


async def run_agent_async(
    prompt: str,
    model_id: Optional[str] = None,
    system_prompt: str = "You are a helpful AI assistant.",
    history: Optional[List[Dict]] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run the agent and collect full response (non-streaming).

    Args:
        prompt: User input prompt
        model_id: LLM model ID (optional, uses default if not provided)
        system_prompt: System prompt for the agent
        history: Conversation history in Strands format
        tool_config: Tool configuration

    Returns:
        Response dictionary with 'response', 'tool_calls', and 'metadata'
    """
    response_text = []
    tool_calls = []
    metadata = {}

    try:
        async for chunk in stream_agent_async(
            prompt=prompt,
            model_id=model_id,
            system_prompt=system_prompt,
            history=history,
            tool_config=tool_config
        ):
            if chunk.get('status') in ('complete', 'error'):
                if chunk.get('status') == 'error':
                    return {
                        'response': f"Error: {chunk.get('error')}",
                        'tool_calls': tool_calls,
                        'metadata': {'error': True},
                        'status': 'error'
                    }
                continue

            if 'text' in chunk:
                response_text.append(chunk['text'])

            if 'tool_use' in chunk:
                tool_calls.append(chunk['tool_use'])

            if 'metadata' in chunk:
                metadata.update(chunk['metadata'])

        return {
            'response': ''.join(response_text),
            'tool_calls': tool_calls,
            'metadata': metadata,
            'status': 'success'
        }

    except Exception as e:
        logger.error(f"Agent execution error: {e}", exc_info=True)
        return {
            'response': f"Error: {str(e)}",
            'tool_calls': [],
            'metadata': {'error': True},
            'status': 'error'
        }


@app.entrypoint
async def handle_request(request: Dict[str, Any]):
    """
    Main entry point for AgentCore Runtime.

    Request format:
    {
        "action": "invoke" | "health",  # default: "invoke"
        "prompt": "User message",
        "model_id": "optional-model-id",
        "system_prompt": "optional system prompt",
        "history": [optional conversation history],
        "tool_config": {optional tool configuration},
        "stream": true | false  # default: false
    }

    Response format (non-streaming):
    {
        "response": "Agent response text",
        "tool_calls": [list of tool calls made],
        "metadata": {additional metadata},
        "status": "success" or "error"
    }

    Response format (streaming - SSE):
    data: {"text": "chunk1"}
    data: {"text": "chunk2"}
    data: {"tool_use": {...}}
    data: {"status": "complete", "event": "done"}
    """
    # Handle different actions
    action = request.get('action', 'invoke')

    # Health check
    if action == 'health':
        return {
            'status': 'healthy',
            'service': 'my-aibox-agent',
            'version': '2.1.0'
        }

    # Default: invoke agent
    prompt = request.get('prompt', '')
    if not prompt:
        return {
            'response': 'Error: prompt is required',
            'tool_calls': [],
            'metadata': {},
            'status': 'error'
        }

    model_id = request.get('model_id')
    system_prompt = request.get('system_prompt', 'You are a helpful AI assistant.')
    history = request.get('history')
    tool_config = request.get('tool_config')
    stream = request.get('stream', False)

    # Streaming mode: return async generator
    if stream:
        async def generate():
            async for chunk in stream_agent_async(
                prompt=prompt,
                model_id=model_id,
                system_prompt=system_prompt,
                history=history,
                tool_config=tool_config
            ):
                yield chunk

        return generate()

    # Non-streaming mode: return full response
    result = await run_agent_async(
        prompt=prompt,
        model_id=model_id,
        system_prompt=system_prompt,
        history=history,
        tool_config=tool_config
    )

    return result


if __name__ == "__main__":
    import os
    import sys

    # Only run test locally, not in AgentCore Runtime
    if not os.environ.get("AWS_EXECUTION_ENV"):
        print("Starting AgentCore app locally...")
        print("Use 'agentcore invoke' to test, or run app.run() for local server")

        async def test_non_streaming():
            """Test non-streaming mode"""
            print("\n=== Testing Non-Streaming Mode ===")
            test_request = {
                "prompt": "What is 2 + 2?",
                "system_prompt": "You are a helpful assistant. Answer briefly.",
                "stream": False
            }
            print(f"Request: {json.dumps(test_request, indent=2)}")
            result = await handle_request(test_request)
            print(f"Result: {json.dumps(result, indent=2)}")

        async def test_streaming():
            """Test streaming mode"""
            print("\n=== Testing Streaming Mode ===")
            test_request = {
                "prompt": "Count from 1 to 5.",
                "system_prompt": "You are a helpful assistant. Answer briefly.",
                "stream": True
            }
            print(f"Request: {json.dumps(test_request, indent=2)}")
            print("Streaming response:")

            generator = await handle_request(test_request)
            async for chunk in generator:
                print(f"  chunk: {json.dumps(chunk)}")

        # Run tests
        if len(sys.argv) > 1 and sys.argv[1] == "--stream":
            asyncio.run(test_streaming())
        elif len(sys.argv) > 1 and sys.argv[1] == "--server":
            print("Starting local server on port 8080...")
            app.run()
        else:
            asyncio.run(test_non_streaming())
    else:
        # In AgentCore Runtime, just run the app
        app.run()
