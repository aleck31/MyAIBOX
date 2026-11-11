"""LLM provider registry: endpoints and credentials, stored in the settings table (`llm_providers`·global)."""
import os
import socket
import time
from typing import Callable, List, Optional

from backend.common.logger import logger
from backend.core.config import env_config
from backend.utils.aws import get_aws_resource
from . import LLMProvider
from .model_list import DEFAULT_PROVIDERS
from .model_manager import model_manager  # noqa: F401  creates the settings table if missing

_KEY = {'setting_name': 'llm_providers', 'type': 'global'}


class ProviderManager:

    def __init__(self):
        self.table = get_aws_resource('dynamodb').Table(env_config.database_config['setting_table'])  # type: ignore
        self._cache: Optional[List[LLMProvider]] = None
        # Called after any change so cached clients and keys are rebuilt from the new settings.
        self._listeners: List[Callable[[], None]] = []
        self._init_default_providers()

    def on_change(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def flush_cache(self) -> None:
        self._cache = None
        for listener in self._listeners:
            listener()

    def get_providers(self) -> List[LLMProvider]:
        if self._cache is None:
            item = self.table.get_item(Key=_KEY).get('Item') or {}
            self._cache = sorted((LLMProvider.from_dict(p) for p in item.get('providers', [])), key=lambda p: p.name)
        return self._cache

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        return next((p for p in self.get_providers() if p.name == name), None)

    def add_provider(self, provider: LLMProvider) -> None:
        providers = self.get_providers()
        if any(p.name == provider.name for p in providers):
            raise ValueError(f"Provider '{provider.name}' already exists")
        self._put([*providers, provider], 'add_provider')

    def update_provider(self, provider: LLMProvider) -> None:
        providers = self.get_providers()
        if not any(p.name == provider.name for p in providers):
            raise ValueError(f"Provider '{provider.name}' not found")
        self._put([provider if p.name == provider.name else p for p in providers], 'update_provider')

    def delete_provider(self, name: str) -> None:
        providers = self.get_providers()
        if not any(p.name == name for p in providers):
            raise ValueError(f"Provider '{name}' not found")
        self._put([p for p in providers if p.name != name], 'delete_provider')

    def _put(self, providers: List[LLMProvider], op: str) -> None:
        self.table.put_item(Item={
            **_KEY,
            'providers': [p.to_dict() for p in providers],
            'modified_at': int(time.time()),
            'modified_by': f"{socket.gethostname()}:pid{os.getpid()}:{op}",
        })
        self.flush_cache()
        logger.info(f"Providers saved ({op})")

    def _init_default_providers(self) -> None:
        """Seed only when the item is absent; a read error must never overwrite the live registry."""
        try:
            if 'Item' in self.table.get_item(Key=_KEY):
                return
            self._put(DEFAULT_PROVIDERS, 'init_default_providers_seed')
        except Exception as e:
            logger.error(f"init_default_providers skipped (read error, registry left intact): {e}")


provider_manager = ProviderManager()
