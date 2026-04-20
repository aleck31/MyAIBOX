"""DrawService — real image generation. VERY slow / costly.

Single minimal test to verify the pipeline works end-to-end.
"""
from __future__ import annotations

import pytest

from core.service.draw_service import DrawService
from genai.models.model_manager import model_manager

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def _init_models():
    model_manager.init_default_models()


async def test_text_to_image_stateless_returns_pil_image():
    from PIL.Image import Image

    svc = DrawService()
    img = await svc.text_to_image_stateless(
        prompt="a simple red circle on white background",
        negative_prompt="",
        seed=42,
        aspect_ratio="1:1",
    )
    assert isinstance(img, Image)
