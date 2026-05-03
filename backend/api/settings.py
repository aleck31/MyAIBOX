# Copyright iX.
# SPDX-License-Identifier: MIT-0
import json
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from core.session.store import SessionStore
from core.module_config import module_config
from genai.models.model_manager import model_manager
from genai.tools.legacy.tool_registry import legacy_tool_registry
from api.auth import get_auth_user
from common.logger import setup_logger

logger = setup_logger('api.settings')

router = APIRouter(prefix="/settings", tags=["settings"])

MODULE_LIST = ['assistant', 'persona', 'text', 'summary', 'vision', 'asking', 'draw']

_session_store = None


def _get_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionStore.get_instance()
    return _session_store


# ─── Account / Sessions ──────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(username: str = Depends(get_auth_user)):
    sessions = await _get_store().list_sessions(username)
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
async def delete_session(session_id: str, username: str = Depends(get_auth_user)):
    await _get_store().delete_session_by_id(session_id)
    return {"ok": True}


class ClearHistoryRequest(BaseModel):
    session_id: str


@router.post("/sessions/clear-history")
async def clear_session_history(body: ClearHistoryRequest, username: str = Depends(get_auth_user)):
    store = _get_store()
    session = await store.get_session_by_id(body.session_id)
    session.history = []
    await store.save_session(session)
    return {"ok": True}


# ─── Module Configuration ────────────────────────────────────────────────────

@router.get("/modules")
async def get_modules(username: str = Depends(get_auth_user)):
    """Return all module configs + available models and tools."""
    all_models = model_manager.get_models()
    model_choices = [
        {"model_id": m.model_id, "name": f"{m.name}, {m.api_provider}"}
        for m in (all_models or [])
    ]
    available_tools = list(legacy_tool_registry.tools.keys())

    modules = {}
    for name in MODULE_LIST:
        cfg = module_config.get_module_config(name) or {}
        params = cfg.get('parameters', {})
        # Convert Decimal to numeric
        params = module_config._decimal_to_numeric(params) if params else {}
        modules[name] = {
            "default_model": cfg.get('default_model', ''),
            "parameters": json.dumps(params, indent=2),
            "enabled_tools": cfg.get('enabled_tools', []),
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


@router.post("/modules/update")
async def update_module(body: ModuleUpdateRequest, username: str = Depends(get_auth_user)):
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
    module_config.update_module_config(body.module_name, cfg)
    return {"ok": True}


# ─── Model Management ────────────────────────────────────────────────────────

@router.get("/models")
async def list_models(username: str = Depends(get_auth_user)):
    models = model_manager.get_models()
    return [
        {
            "name": m.name, "model_id": m.model_id, "api_provider": m.api_provider,
            "vendor": m.vendor, "category": m.category, "description": m.description or "",
            "region": m.region or "",
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
    api_provider: str = "Bedrock"
    vendor: str = ""
    category: str = "text"
    description: str = ""
    region: str = ""
    input_modality: List[str] = ["text"]
    output_modality: List[str] = ["text"]
    streaming: bool = True
    tool_use: bool = False
    reasoning: bool = False
    context_window: int = 131072


@router.post("/models/add")
async def add_model(body: ModelRequest, username: str = Depends(get_auth_user)):
    from genai.models import LLMModel, LLM_CAPABILITIES
    try:
        caps = LLM_CAPABILITIES(
            input_modality=body.input_modality, output_modality=body.output_modality,
            streaming=body.streaming, tool_use=body.tool_use,
            reasoning=body.reasoning, context_window=body.context_window,
        )
        model = LLMModel(
            name=body.name, model_id=body.model_id, api_provider=body.api_provider,
            vendor=body.vendor, category=body.category, description=body.description,
            region=body.region, capabilities=caps,
        )
        model_manager.add_model(model)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/models/update")
async def update_model(body: ModelRequest, username: str = Depends(get_auth_user)):
    from genai.models import LLMModel, LLM_CAPABILITIES
    try:
        caps = LLM_CAPABILITIES(
            input_modality=body.input_modality, output_modality=body.output_modality,
            streaming=body.streaming, tool_use=body.tool_use,
            reasoning=body.reasoning, context_window=body.context_window,
        )
        model = LLMModel(
            name=body.name, model_id=body.model_id, api_provider=body.api_provider,
            vendor=body.vendor, category=body.category, description=body.description,
            region=body.region, capabilities=caps,
        )
        model_manager.update_model(model)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/models/{model_id:path}")
async def delete_model(model_id: str, username: str = Depends(get_auth_user)):
    try:
        model_manager.delete_model_by_id(model_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── MCP Server Management ───────────────────────────────────────────────────

@router.get("/mcp-servers")
async def list_mcp_servers(username: str = Depends(get_auth_user)):
    from genai.tools.mcp.mcp_server_manager import mcp_server_manager
    from genai.tools.provider import tool_provider
    servers = mcp_server_manager.get_mcp_servers()
    # Pre-compute per-server tool counts
    try:
        all_tools = tool_provider.list_tools()
        mcp_tools = [t for t in all_tools if t.get('type') == 'mcp_server']
    except Exception:
        mcp_tools = []
    result = []
    for name, cfg in servers.items():
        stype = cfg.get('type', 'unknown')
        if stype == 'stdio':
            cmd = cfg.get('command', '')
            args = cfg.get('args', [])
            url = f"{cmd} {' '.join(str(a) for a in args)}".strip()
        else:
            url = cfg.get('url', '')
        tools_count = len([t for t in mcp_tools if t['name'] == name]) if not cfg.get('disabled') else 0
        result.append({
            "name": name, "type": stype,
            "status": "Disabled" if cfg.get('disabled') else "Enabled",
            "url": url, "tools_count": tools_count,
        })
    return result


class McpServerRequest(BaseModel):
    name: str
    type: str = "http"
    url: str = ""
    args: str = ""


@router.post("/mcp-servers/add")
async def add_mcp_server(body: McpServerRequest, username: str = Depends(get_auth_user)):
    from genai.tools.mcp.mcp_server_manager import mcp_server_manager
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
async def delete_mcp_server(server_name: str, username: str = Depends(get_auth_user)):
    from genai.tools.mcp.mcp_server_manager import mcp_server_manager
    try:
        mcp_server_manager.delete_mcp_server(server_name)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class McpToggleRequest(BaseModel):
    name: str
    disabled: bool


@router.post("/mcp-servers/toggle")
async def toggle_mcp_server(body: McpToggleRequest, username: str = Depends(get_auth_user)):
    from genai.tools.mcp.mcp_server_manager import mcp_server_manager
    try:
        cfg = mcp_server_manager.get_mcp_server(body.name)
        if not cfg:
            return {"ok": False, "error": "Server not found"}
        cfg["disabled"] = body.disabled
        mcp_server_manager.update_mcp_server(body.name, cfg)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
