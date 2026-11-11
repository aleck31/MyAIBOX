# Copyright iX.
# SPDX-License-Identifier: MIT-0
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from backend.core.session.store import SessionStore
from backend.core.module_config import module_config
from backend.genai.models import LLMModel, LLMProvider, LLM_CAPABILITIES, VALID_APIS
from backend.genai.models.model_manager import model_manager
from backend.genai.models.provider_manager import provider_manager
from backend.genai.tools.legacy.tool_registry import legacy_tool_registry
from backend.api.auth import get_auth_user, is_admin
from backend.common.logger import setup_logger
from backend.core.config import app_config

logger = setup_logger('api.settings')

router = APIRouter(prefix="/settings", tags=["settings"])

# Tool modules — pure-function features with their own frontend pages and
# API routes. Chat-module agents (Assistant, 家庭医生, etc.) are configured
# separately via /settings/agents.
MODULE_LIST = ['text', 'summary', 'vision', 'asking', 'draw']

_session_store = None


def _get_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionStore.get_instance()
    return _session_store


# ─── Account / Sessions ──────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(sub: str = Depends(get_auth_user)):
    sessions = await _get_store().list_sessions(sub)
    return [
        {
            "module": s.metadata.module_name,
            "session_id": s.session_id,
            "records": len(s.history),
            "created": s.created_time.isoformat(),
            "updated": s.updated_time.isoformat(),
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, sub: str = Depends(get_auth_user)):
    await _get_store().delete_session_by_id(session_id)
    return {"ok": True}


class ClearHistoryRequest(BaseModel):
    session_id: str


@router.post("/sessions/clear-history")
async def clear_session_history(body: ClearHistoryRequest, sub: str = Depends(get_auth_user)):
    store = _get_store()
    session = await store.get_session_by_id(body.session_id)
    session.history = []
    await store.save_session(session)
    return {"ok": True}


# ─── Module Configuration ────────────────────────────────────────────────────

@router.get("/modules")
async def get_modules(sub: str = Depends(get_auth_user)):
    """Return all module configs + available models and tools."""
    def _choice(m):
        # `reasoning` lets the UI show the Thinking controls only for capable models.
        return {"model_id": m.model_id, "name": f"{m.name}, {m.provider}",
                "reasoning": bool(m.capabilities.reasoning)}

    model_choices = [_choice(m) for m in (model_manager.get_models() or [])]
    available_tools = list(legacy_tool_registry.tools.keys())

    modules = {}
    for name in MODULE_LIST:
        cfg = module_config.get_module_config(name) or {}
        params = cfg.get('parameters', {})
        # Convert Decimal to numeric
        params = module_config._decimal_to_numeric(params) if params else {}
        thinking = cfg.get('thinking', {})
        thinking = module_config._decimal_to_numeric(thinking) if thinking else {}
        # Each module's own eligible models (same filter its page uses), so the
        # ModuleCard dropdown can't offer models the module can't run.
        eligible = model_manager.get_models(filter=module_config.get_model_filter(name)) or []
        modules[name] = {
            "default_model": cfg.get('default_model', ''),
            "parameters": json.dumps(params, indent=2),
            "enabled_tools": cfg.get('enabled_tools', []),
            "thinking": thinking,
            "models": [_choice(m) for m in eligible],
        }

    return {
        "modules": modules,
        "model_choices": model_choices,
        "available_tools": available_tools,
    }


class ModuleUpdateRequest(BaseModel):
    module_name: str
    default_model: str
    parameters: str  # JSON string
    enabled_tools: List[str]
    # Model-agnostic thinking intent {enabled, effort}; absent for non-reasoning modules.
    thinking: Optional[Dict[str, Any]] = None


@router.post("/modules/update")
async def update_module(body: ModuleUpdateRequest, sub: str = Depends(get_auth_user)):
    try:
        params = json.loads(body.parameters)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Invalid JSON: {e}"}

    cfg = module_config.get_module_config(body.module_name) or {}
    cfg.update({
        'default_model': body.default_model,
        'parameters': params,
        'enabled_tools': body.enabled_tools,
    })
    if body.thinking is not None:
        cfg['thinking'] = body.thinking
    module_config.update_module_config(body.module_name, cfg)
    return {"ok": True}


# ─── Model Management ────────────────────────────────────────────────────────

@router.get("/models")
async def list_models(refresh: bool = False, sub: str = Depends(get_auth_user)):
    # Models are cached in-process; DDB changes outside the app won't show up until the cache is flushed.
    if refresh:
        model_manager.flush_cache()
        provider_manager.flush_cache()
    models = model_manager.get_models(include_disabled=True)
    return [
        {
            "name": m.name, "model_id": m.model_id, "provider": m.provider, "api": m.api,
            "vendor": m.vendor, "category": m.category, "description": m.description or "",
            "enabled": m.enabled, "service_tier": m.service_tier or "",
            "capabilities": {
                "input_modality": m.capabilities.input_modality,
                "output_modality": m.capabilities.output_modality,
                "streaming": m.capabilities.streaming,
                "tool_use": m.capabilities.tool_use,
                "reasoning": m.capabilities.reasoning,
                "context_window": m.capabilities.context_window,
            }
        }
        for m in (models or [])
    ]


class ModelRequest(BaseModel):
    name: str
    model_id: str
    provider: str
    api: str
    vendor: str = ""
    category: str = "text"
    description: str = ""
    service_tier: str = ""
    input_modality: List[str] = ["text"]
    output_modality: List[str] = ["text"]
    streaming: bool = True
    tool_use: bool = False
    reasoning: bool = False
    context_window: int = 131072
    enabled: bool = True


def _model_from_request(body: ModelRequest) -> LLMModel:
    provider = provider_manager.get_provider(body.provider)
    if not provider:
        raise ValueError(f"Provider '{body.provider}' does not exist")
    if body.api not in provider.apis:
        raise ValueError(f"Provider '{provider.name}' does not serve the {body.api} API")
    caps = LLM_CAPABILITIES(
        input_modality=body.input_modality, output_modality=body.output_modality,
        streaming=body.streaming, tool_use=body.tool_use,
        reasoning=body.reasoning, context_window=body.context_window,
    )
    return LLMModel(
        name=body.name, model_id=body.model_id, provider=body.provider, api=body.api,
        vendor=body.vendor, category=body.category, description=body.description,
        enabled=body.enabled, service_tier=body.service_tier, capabilities=caps,
    )


@router.post("/models/add")
async def add_model(body: ModelRequest, sub: str = Depends(get_auth_user)):
    try:
        model_manager.add_model(_model_from_request(body))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/models/update")
async def update_model(body: ModelRequest, sub: str = Depends(get_auth_user)):
    try:
        model_manager.update_model(_model_from_request(body))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/models/{model_id:path}")
async def delete_model(model_id: str, sub: str = Depends(get_auth_user)):
    try:
        model_manager.delete_model_by_id(model_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class ToggleModelRequest(BaseModel):
    enabled: bool


@router.post("/models/toggle/{model_id:path}")
async def toggle_model(model_id: str, body: ToggleModelRequest, sub: str = Depends(get_auth_user)):
    try:
        model_manager.toggle_model_by_id(model_id, body.enabled)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── LLM Providers ───────────────────────────────────────────────────────────

def _provider_view(p: LLMProvider) -> Dict[str, Any]:
    # An inline key never leaves the server; the UI only learns whether one is set.
    return {"name": p.name, "auth": p.auth, "apis": p.apis, "base_url": p.base_url, "region": p.region,
            "secret_name": p.secret_name, "has_api_key": bool(p.api_key),
            "models": [m.model_id for m in model_manager.get_models(include_disabled=True) if m.provider == p.name]}


@router.get("/providers")
async def list_providers(refresh: bool = False, sub: str = Depends(get_auth_user)):
    if refresh:
        provider_manager.flush_cache()
    return {"providers": [_provider_view(p) for p in provider_manager.get_providers()],
            "apis": list(VALID_APIS), "can_edit": is_admin(sub)}


class ProviderRequest(BaseModel):
    name: str
    auth: str
    apis: List[str]
    base_url: str = ""
    region: str = ""
    secret_name: str = ""
    # None keeps the stored key; "" clears it.
    api_key: Optional[str] = None


def _provider_write_denied(sub: str) -> Optional[JSONResponse]:
    """Providers hold credentials for every user's model calls: admins only, and closed when ADMIN_SUBS is unset."""
    if is_admin(sub):
        return None
    logger.warning(f"[settings] provider write denied for sub [{sub}]")
    return JSONResponse({"ok": False, "error": "Admin only (ADMIN_SUBS)"}, status_code=403)


def _provider_from_request(body: ProviderRequest, existing: Optional[LLMProvider]) -> LLMProvider:
    api_key = (existing.api_key if existing else "") if body.api_key is None else body.api_key.strip()
    if body.secret_name.strip():
        api_key = ""
    return LLMProvider(name=body.name.strip(), auth=body.auth, apis=body.apis, base_url=body.base_url.strip(),
                       region=body.region.strip(), secret_name=body.secret_name.strip(), api_key=api_key)


def _apis_still_used(provider: LLMProvider) -> List[str]:
    """Models that would lose their API if the provider stopped serving it."""
    return [m.model_id for m in model_manager.get_models(include_disabled=True)
            if m.provider == provider.name and m.api not in provider.apis]


@router.post("/providers/add")
async def add_provider(body: ProviderRequest, sub: str = Depends(get_auth_user)):
    if denied := _provider_write_denied(sub):
        return denied
    try:
        provider_manager.add_provider(_provider_from_request(body, None))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/providers/update")
async def update_provider(body: ProviderRequest, sub: str = Depends(get_auth_user)):
    if denied := _provider_write_denied(sub):
        return denied
    try:
        provider = _provider_from_request(body, provider_manager.get_provider(body.name))
        if orphans := _apis_still_used(provider):
            raise ValueError(f"Models still use the APIs being removed: {', '.join(orphans)}")
        provider_manager.update_provider(provider)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/providers/{name}")
async def delete_provider(name: str, sub: str = Depends(get_auth_user)):
    if denied := _provider_write_denied(sub):
        return denied
    try:
        if used := [m.model_id for m in model_manager.get_models(include_disabled=True) if m.provider == name]:
            raise ValueError(f"Models still use this provider: {', '.join(used)}")
        provider_manager.delete_provider(name)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── MCP Server Management ───────────────────────────────────────────────────

@router.get("/mcp-servers")
async def list_mcp_servers(sub: str = Depends(get_auth_user)):
    from backend.genai.tools.mcp.mcp_server_manager import mcp_server_manager
    servers = mcp_server_manager.get_mcp_servers()
    result = []
    for name, cfg in servers.items():
        stype = cfg.get('type', 'unknown')
        if stype == 'stdio':
            cmd = cfg.get('command', '')
            args = cfg.get('args', [])
            url = f"{cmd} {' '.join(str(a) for a in args)}".strip()
        else:
            url = cfg.get('url', '')
        result.append({
            "name": name, "type": stype,
            "status": "Disabled" if cfg.get('disabled') else "Enabled",
            "url": url,
        })
    return result


def _mcp_write_denied(sub: str, server_type: str = "") -> Optional[JSONResponse]:
    """Gate MCP config writes; returns a 403 response when denied, else None.

    stdio servers spawn processes on the host, so:
    - ADMIN_SUBS set   -> every MCP write requires an admin.
    - ADMIN_SUBS unset -> fail closed for stdio (http/sse stay open to any logged-in user).

    The body keeps the `{ok, error}` shape the frontend already renders.
    """
    if app_config.admin_subs:
        error = None if is_admin(sub) else "Admin only"
    elif server_type == "stdio":
        error = "Adding stdio MCP servers requires ADMIN_SUBS to be configured"
    else:
        error = None
    if error:
        logger.warning(f"[settings] MCP write denied for sub [{sub}]: {error}")
        return JSONResponse({"ok": False, "error": error}, status_code=403)
    return None


class McpServerRequest(BaseModel):
    name: str
    type: str = "http"
    url: str = ""
    args: str = ""


@router.post("/mcp-servers/add")
async def add_mcp_server(body: McpServerRequest, sub: str = Depends(get_auth_user)):
    if denied := _mcp_write_denied(sub, body.type):
        return denied
    from backend.genai.tools.mcp.mcp_server_manager import mcp_server_manager
    try:
        config: dict = {"type": body.type, "disabled": False}
        if body.type in ("http", "sse"):
            config["url"] = body.url
        elif body.type == "stdio":
            config["command"] = body.url
            config["args"] = json.loads(body.args) if body.args.strip() else []
        mcp_server_manager.add_mcp_server(body.name, config)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/mcp-servers/{server_name}")
async def delete_mcp_server(server_name: str, sub: str = Depends(get_auth_user)):
    if denied := _mcp_write_denied(sub):
        return denied
    from backend.genai.tools.mcp.mcp_server_manager import mcp_server_manager
    try:
        mcp_server_manager.delete_mcp_server(server_name)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class McpToggleRequest(BaseModel):
    name: str
    disabled: bool


@router.post("/mcp-servers/toggle")
async def toggle_mcp_server(body: McpToggleRequest, sub: str = Depends(get_auth_user)):
    if denied := _mcp_write_denied(sub):
        return denied
    from backend.genai.tools.mcp.mcp_server_manager import mcp_server_manager
    try:
        cfg = mcp_server_manager.get_mcp_server(body.name)
        if not cfg:
            return {"ok": False, "error": "Server not found"}
        cfg["disabled"] = body.disabled
        mcp_server_manager.update_mcp_server(body.name, cfg)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
