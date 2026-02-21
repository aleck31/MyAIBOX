# Copyright iX.
# SPDX-License-Identifier: MIT-0
"""
AgentCore Runtime Client for calling deployed AI Agent.

This module provides a client to invoke AgentCore Runtime deployed agents,
supporting both streaming (SSE) and non-streaming responses.
"""
import json
import asyncio
import requests
from typing import Dict, Any, Optional, List, AsyncIterator
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from common.logger import logger
from core.config import env_config
from utils.aws import get_aws_session


class AgentCoreClient:
    """Client for invoking AgentCore Runtime deployed agents.

    Supports:
    - HTTP SSE streaming for real-time responses
    - AWS SigV4 authentication
    - Same interface as AgentProvider for easy switching
    """

    def __init__(
        self,
        runtime_arn: str,
        region: Optional[str] = None,
        endpoint_name: str = "DEFAULT"
    ):
        """Initialize AgentCore client.

        Args:
            runtime_arn: Full ARN of the AgentCore runtime
            region: AWS region (default: from config)
            endpoint_name: Endpoint qualifier (default: DEFAULT)
        """
        self.runtime_arn = runtime_arn
        self.region = region or env_config.aws_region
        self.endpoint_name = endpoint_name

        # Parse ARN to get runtime ID
        self._parse_runtime_arn()

        # Build endpoint URL
        self.endpoint_url = self._build_endpoint_url()

    def _parse_runtime_arn(self):
        """Parse runtime ARN and extract components."""
        # Expected format: arn:aws:bedrock-agentcore:{region}:{account}:runtime/{runtime_id}
        parts = self.runtime_arn.split(":")
        if len(parts) != 6:
            raise ValueError(f"Invalid runtime ARN format: {self.runtime_arn}")

        self.account_id = parts[4]
        resource = parts[5]
        if resource.startswith("runtime/"):
            self.runtime_id = resource.split("/", 1)[1]
        else:
            raise ValueError(f"Invalid runtime ARN format: {self.runtime_arn}")

    def _build_endpoint_url(self) -> str:
        """Build the AgentCore invocation endpoint URL."""
        from urllib.parse import quote
        encoded_arn = quote(self.runtime_arn, safe="")
        host = f"bedrock-agentcore.{self.region}.amazonaws.com"
        return f"https://{host}/runtimes/{encoded_arn}/invocations"

    def _sign_request(self, method: str, url: str, body: str) -> Dict[str, str]:
        """Sign request with AWS SigV4.

        Args:
            method: HTTP method
            url: Request URL
            body: Request body (string)

        Returns:
            Headers with SigV4 signature
        """
        session = get_aws_session(region_name=self.region)
        credentials = session.get_credentials()
        frozen_credentials = credentials.get_frozen_credentials()

        # Create AWS request for signing
        request = AWSRequest(
            method=method,
            url=url,
            data=body,
            headers={"Content-Type": "application/json"}
        )

        # Sign with SigV4
        auth = SigV4Auth(frozen_credentials, "bedrock-agentcore", self.region)
        auth.add_auth(request)

        return dict(request.headers)

    async def generate_stream(
        self,
        prompt: str,
        history_messages: Optional[List] = None,
        tool_config: Optional[Dict] = None,
        model_id: Optional[str] = None,
        system_prompt: str = "You are a helpful AI assistant."
    ) -> AsyncIterator[Dict]:
        """Stream responses from AgentCore Runtime.

        This method has the same interface as AgentProvider.generate_stream()
        for easy switching between local and remote execution.

        Args:
            prompt: User input prompt
            history_messages: Conversation history
            tool_config: Tool configuration
            model_id: Optional model ID override
            system_prompt: System prompt

        Yields:
            Response chunks in the same format as AgentProvider
        """
        # Build request payload
        payload = {
            "prompt": prompt,
            "stream": True,
            "system_prompt": system_prompt,
        }

        if history_messages:
            payload["history"] = history_messages
        if tool_config:
            payload["tool_config"] = tool_config
        if model_id:
            payload["model_id"] = model_id

        body = json.dumps(payload)

        # Sign request
        signed_headers = self._sign_request("POST", self.endpoint_url, body)

        logger.info(f"Calling AgentCore Runtime (streaming): {self.runtime_id}")

        try:
            # Use requests with streaming in a thread pool
            response = await asyncio.to_thread(
                self._make_streaming_request,
                body,
                signed_headers
            )

            if response.status_code != 200:
                logger.error(f"AgentCore error: {response.status_code} - {response.text}")
                yield {
                    "text": f"Error calling AgentCore: {response.status_code}",
                    "metadata": {"error": True}
                }
                return

            # Parse SSE stream
            for chunk in self._parse_sse_stream_sync(response):
                yield chunk

        except requests.RequestException as e:
            logger.error(f"HTTP error calling AgentCore: {e}")
            yield {
                "text": f"Connection error: {str(e)}",
                "metadata": {"error": True}
            }
        except Exception as e:
            logger.error(f"Unexpected error calling AgentCore: {e}", exc_info=True)
            yield {
                "text": f"Error: {str(e)}",
                "metadata": {"error": True}
            }

    def _make_streaming_request(self, body: str, headers: Dict[str, str]) -> requests.Response:
        """Make streaming HTTP request (synchronous, called from thread pool).

        Args:
            body: Request body
            headers: Signed headers

        Returns:
            requests.Response object with streaming enabled
        """
        return requests.post(
            self.endpoint_url,
            data=body,
            headers=headers,
            stream=True,
            timeout=600  # 10 min timeout
        )

    def _parse_sse_stream_sync(self, response: requests.Response):
        """Parse Server-Sent Events stream synchronously.

        Args:
            response: requests.Response object with streaming

        Yields:
            Parsed event data as dicts
        """
        buffer = ""

        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                buffer += chunk

                # Process complete events (separated by double newline)
                while "\n\n" in buffer:
                    event, buffer = buffer.split("\n\n", 1)

                    # Parse SSE event
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix
                            try:
                                data = json.loads(data_str)

                                # Check for completion/error status
                                if data.get("status") == "complete":
                                    logger.debug("AgentCore stream complete")
                                    return
                                elif data.get("status") == "error":
                                    logger.error(f"AgentCore stream error: {data.get('error')}")
                                    yield {
                                        "text": f"Error: {data.get('error', 'Unknown error')}",
                                        "metadata": {"error": True}
                                    }
                                    return

                                # Yield the chunk as-is (already in our format)
                                yield data

                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse SSE data: {e}")
                                continue

    async def invoke(
        self,
        prompt: str,
        history_messages: Optional[List] = None,
        tool_config: Optional[Dict] = None,
        model_id: Optional[str] = None,
        system_prompt: str = "You are a helpful AI assistant."
    ) -> Dict[str, Any]:
        """Invoke AgentCore Runtime and get full response (non-streaming).

        Args:
            prompt: User input prompt
            history_messages: Conversation history
            tool_config: Tool configuration
            model_id: Optional model ID override
            system_prompt: System prompt

        Returns:
            Full response dict with 'response', 'tool_calls', 'metadata', 'status'
        """
        # Build request payload
        payload = {
            "prompt": prompt,
            "stream": False,
            "system_prompt": system_prompt,
        }

        if history_messages:
            payload["history"] = history_messages
        if tool_config:
            payload["tool_config"] = tool_config
        if model_id:
            payload["model_id"] = model_id

        body = json.dumps(payload)

        # Sign request
        signed_headers = self._sign_request("POST", self.endpoint_url, body)

        logger.info(f"Invoking AgentCore Runtime (non-streaming): {self.runtime_id}")

        try:
            response = await asyncio.to_thread(
                requests.post,
                self.endpoint_url,
                data=body,
                headers=signed_headers,
                timeout=600
            )

            if response.status_code != 200:
                logger.error(f"AgentCore error: {response.status_code} - {response.text}")
                return {
                    "response": f"Error: {response.status_code}",
                    "tool_calls": [],
                    "metadata": {"error": True},
                    "status": "error"
                }

            return response.json()

        except Exception as e:
            logger.error(f"Error invoking AgentCore: {e}", exc_info=True)
            return {
                "response": f"Error: {str(e)}",
                "tool_calls": [],
                "metadata": {"error": True},
                "status": "error"
            }

    async def health_check(self) -> Dict[str, Any]:
        """Check AgentCore Runtime health.

        Returns:
            Health status dict
        """
        payload = {"action": "health"}
        body = json.dumps(payload)

        signed_headers = self._sign_request("POST", self.endpoint_url, body)

        try:
            response = await asyncio.to_thread(
                requests.post,
                self.endpoint_url,
                data=body,
                headers=signed_headers,
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "unhealthy", "error": response.status_code}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
