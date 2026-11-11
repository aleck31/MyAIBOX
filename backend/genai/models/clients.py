"""SDK clients for a model, built from its provider's endpoint and credentials."""
import ast
import json
from typing import Dict
from urllib.parse import urlparse

import boto3
from botocore import UNSIGNED
from botocore.config import Config

from backend.common.errors import ModelUnavailableError
from backend.utils.aws import get_aws_client, get_aws_session
from . import AUTH_AWS, LLMModel, LLMProvider
from .model_manager import model_manager
from .provider_manager import provider_manager

# Flex-tier requests can queue before the first token, longer than boto's default 60s read timeout.
_BOTO_TIMEOUTS = dict(read_timeout=300, retries={"max_attempts": 10, "mode": "standard"})
_keys: Dict[str, str] = {}
_bearer_sessions: Dict[str, boto3.Session] = {}
# Bumped on every provider or model change; holders of long-lived clients compare it to rebuild them.
_generation = 0


def _forget_clients() -> None:
    global _generation
    _keys.clear()
    _bearer_sessions.clear()
    _generation += 1


def generation() -> int:
    return _generation


def on_change(listener) -> None:
    """Call `listener` after any provider or model change, e.g. to drop cached clients."""
    provider_manager.on_change(listener)
    model_manager.on_change(listener)


on_change(_forget_clients)


def resolve(model_id: str) -> tuple[LLMModel, LLMProvider]:
    """The model and its provider; raises if either is missing or the provider does not serve the model's API."""
    model = model_manager.get_model_by_id(model_id)
    if not model:
        raise ModelUnavailableError(model_id)
    provider = provider_manager.get_provider(model.provider)
    if not provider:
        raise ValueError(f"Model {model_id} uses provider '{model.provider}', which does not exist")
    if model.api not in provider.apis:
        raise ValueError(f"Provider '{provider.name}' does not serve {model.api} (model {model_id})")
    return model, provider


def api_key(provider: LLMProvider) -> str:
    if provider.api_key:
        return provider.api_key
    if provider.name not in _keys:
        raw = get_aws_client('secretsmanager').get_secret_value(SecretId=provider.secret_name)['SecretString']
        key = _key_from_secret(raw)
        if not key:
            raise ValueError(f"Secret {provider.secret_name} has no api_key")
        _keys[provider.name] = key
    return _keys[provider.name]


def _key_from_secret(raw: str) -> str:
    """{"api_key": ...} as JSON or as a Python dict repr (older secrets), else the bare key."""
    for parse in (json.loads, ast.literal_eval):
        try:
            value = parse(raw)
        except (ValueError, SyntaxError):
            continue
        if isinstance(value, dict):
            return value.get('api_key') or ''
    return raw.strip()


def _bearer_session(provider: LLMProvider) -> boto3.Session:
    """A session of its own whose bedrock-runtime clients send the key instead of SigV4."""
    if provider.name not in _bearer_sessions:
        session = boto3.Session(region_name=provider.region or 'us-east-1')
        key = api_key(provider)

        def add_bearer(request, **_):
            request.headers['Authorization'] = f'Bearer {key}'

        session.events.register('before-send.bedrock-runtime', add_bearer)
        _bearer_sessions[provider.name] = session
    return _bearer_sessions[provider.name]


def bedrock_kwargs(provider: LLMProvider) -> Dict:
    """boto_session / boto_client_config / endpoint_url, as Strands' BedrockModel takes them."""
    if provider.auth == AUTH_AWS:
        kwargs: Dict = {"boto_session": get_aws_session(region_name=provider.region),
                        "boto_client_config": Config(**_BOTO_TIMEOUTS)}
    else:
        kwargs = {"boto_session": _bearer_session(provider),
                  "boto_client_config": Config(signature_version=UNSIGNED, **_BOTO_TIMEOUTS)}
    if provider.base_url:
        kwargs["endpoint_url"] = provider.base_url.rstrip('/')
    return kwargs


def bedrock_runtime_client(provider: LLMProvider):
    kw = bedrock_kwargs(provider)
    return kw["boto_session"].client('bedrock-runtime', config=kw["boto_client_config"],
                                     endpoint_url=kw.get("endpoint_url"))


def openai_client_args(provider: LLMProvider) -> Dict:
    """OpenAI SDK arguments. A bare host (a gateway root such as agw) gets the SDK's /v1; a URL with a path
    (Bedrock Mantle's /openai/v1, Gemini's /v1beta/openai) is used as given."""
    args: Dict = {"api_key": api_key(provider)}
    if base := provider.base_url.rstrip('/'):
        args["base_url"] = base if urlparse(base).path else f"{base}/v1"
    return args


def gemini_client_args(provider: LLMProvider) -> Dict:
    from google.genai import types
    args: Dict = {"api_key": api_key(provider)}
    if provider.base_url:
        args["http_options"] = types.HttpOptions(base_url=provider.base_url.rstrip('/'))
    return args
