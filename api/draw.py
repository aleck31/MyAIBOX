# Copyright iX.
# SPDX-License-Identifier: MIT-0
import os
import uuid
import time
import random
from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from core.service.service_factory import ServiceFactory
from core.service.draw_service import DrawService
from genai.models.model_manager import model_manager
from api.auth import get_auth_user
from api.prompts.draw import PROMPT_OPTIMIZER_TEMPLATE, NEGATIVE_PROMPTS
from common.logger import setup_logger
import json
import re

logger = setup_logger('api.draw')

router = APIRouter(prefix="/draw", tags=["draw"])

_draw_service: DrawService | None = None
_gen_service = None

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

GENERATED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/generated/images")
os.makedirs(GENERATED_DIR, exist_ok=True)

IMAGE_STYLES = [
    "增强(enhance)", "照片(photographic)", "水墨(ink-wash)", "电影(cinematic)",
    "数字艺术(digital-art)", "美式漫画(comic-book)", "动漫(anime)", "3D模型(3d-model)", "低多边形(low-poly)",
    "扁平插画(flat-illustration)", "超现实(surrealism)", "赛博朋克(cyberpunk)", "素描(sketch)",
    "奇幻艺术(fantasy-art)", "复古海报(retro-poster)", "水彩(watercolor)", "油画(oil-painting)"
]
IMAGE_RATIOS = ['16:9', '5:4', '3:2', '21:9', '1:1', '2:3', '4:5', '9:16', '9:21']
IMAGE_RESOLUTIONS = ['1K', '2K', '4K']


def get_draw_service() -> DrawService:
    global _draw_service
    if _draw_service is None:
        _draw_service = ServiceFactory.create_draw_service('draw')
    return _draw_service


def get_gen_service():
    global _gen_service
    if _gen_service is None:
        _gen_service = ServiceFactory.create_gen_service('text')
    return _gen_service


class DrawRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    style: str = "增强(enhance)"
    ratio: str = "1:1"
    seed: int = 0
    random_seed: bool = True
    model_id: str | None = None
    resolution: str = "1K"


class OptimizeRequest(BaseModel):
    prompt: str
    style: str = "增强(enhance)"
    model_id: str | None = None


@router.get("/config")
async def get_config(username: str = Depends(get_auth_user)):
    """Return available image models, styles, and ratios."""
    models = model_manager.get_models(filter={'category': 'image'})
    return {
        "models": [
            {"model_id": m.model_id, "name": f"{m.name}, {m.api_provider}"}
            for m in (models or [])
        ],
        "styles": IMAGE_STYLES,
        "ratios": IMAGE_RATIOS,
        "resolutions": IMAGE_RESOLUTIONS,
    }


@router.post("/optimize")
async def optimize_prompt(
    body: OptimizeRequest,
    username: str = Depends(get_auth_user),
):
    """Optimize prompt using LLM."""
    if not body.prompt.strip():
        return {"prompt": "", "negative_prompt": ""}

    try:
        # Extract style name from parentheses
        pattern = r'\((.*?)\)'
        match = re.findall(pattern, body.style)
        style_name = match[0] if match else body.style

        # Resolve model name for prompt optimization
        model_name = "AI image generation"
        if body.model_id:
            model = model_manager.get_model_by_id(body.model_id)
            if model:
                model_name = f"{model.name} ({model.api_provider})"

        gen_service = get_gen_service()
        system_prompt = PROMPT_OPTIMIZER_TEMPLATE.format(style=style_name, model=model_name)
        response = await gen_service.gen_text_stateless(
            content={"text": body.prompt},
            system_prompt=system_prompt,
            option_params={"temperature": 0.7, "max_tokens": 800},
        )

        # Try parse JSON (strip markdown code fences if present)
        default_negative = ", ".join(NEGATIVE_PROMPTS)
        text = response.strip()
        if text.startswith("```"):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text).strip()
        try:
            result = json.loads(text)
            return {
                "prompt": result.get("prompt", body.prompt),
                "negative_prompt": result.get("negative_prompt", default_negative),
            }
        except json.JSONDecodeError:
            return {"prompt": text, "negative_prompt": default_negative}

    except Exception as e:
        logger.error(f"Optimize error for {username}: {e}", exc_info=True)
        return {"prompt": body.prompt, "negative_prompt": ", ".join(NEGATIVE_PROMPTS)}


@router.post("/generate")
async def generate_image(
    body: DrawRequest,
    username: str = Depends(get_auth_user),
):
    """Generate image and return file URL."""
    try:
        service = get_draw_service()
        used_seed = random.randrange(1, 4294967295) if body.random_seed else (body.seed or 0)
        negative = body.negative_prompt or ", ".join(NEGATIVE_PROMPTS)

        image = await service.text_to_image_stateless(
            prompt=body.prompt,
            negative_prompt=negative,
            seed=used_seed,
            aspect_ratio=body.ratio,
            model_id=body.model_id,
            resolution=body.resolution,
        )

        # Save to file
        file_id = f"img_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
        path = os.path.join(GENERATED_DIR, file_id)
        image.save(path, format="PNG")

        logger.info(f"Draw OK for {username}: {file_id} seed={used_seed}")
        return {"ok": True, "url": f"/api/draw/image/{file_id}", "seed": used_seed}

    except Exception as e:
        logger.error(f"Draw error for {username}: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/edit")
async def edit_image(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    model_id: str = Form(""),
    ratio: str = Form("1:1"),
    resolution: str = Form("1K"),
    username: str = Depends(get_auth_user),
):
    """Edit image with text instruction."""
    try:
        service = get_draw_service()
        image_data = await image.read()

        result = await service.edit_image(
            image_data=image_data,
            prompt=prompt,
            aspect_ratio=ratio,
            model_id=model_id or None,
            resolution=resolution,
        )

        file_id = f"edit_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
        path = os.path.join(GENERATED_DIR, file_id)
        result.save(path, format="PNG")

        logger.info(f"Edit OK for {username}: {file_id}")
        return {"ok": True, "url": f"/api/draw/image/{file_id}"}

    except Exception as e:
        logger.error(f"Edit error for {username}: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.get("/image/{file_id}")
async def get_image(file_id: str, username: str = Depends(get_auth_user)):
    """Serve generated image."""
    path = os.path.join(GENERATED_DIR, file_id)
    if not os.path.exists(path):
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(path, media_type="image/png")
