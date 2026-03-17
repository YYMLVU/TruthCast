from __future__ import annotations

import base64
import json
import os
from urllib import error, request

from app.schemas.multimodal import ImageOCRResult, OCRBlock, StoredImageRecord
from app.services.json_utils import safe_json_loads


def extract_with_vision_llm(image: StoredImageRecord, timeout_sec: float) -> ImageOCRResult:
    api_key = os.getenv("TRUTHCAST_OCR_LLM_API_KEY", os.getenv("TRUTHCAST_LLM_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("vision llm api key is required")

    base_url = os.getenv("TRUTHCAST_OCR_LLM_BASE_URL", os.getenv("TRUTHCAST_LLM_BASE_URL", "https://api.openai.com/v1")).strip()
    model = os.getenv("TRUTHCAST_OCR_LLM_MODEL", os.getenv("TRUTHCAST_LLM_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    endpoint = base_url.rstrip("/") + "/chat/completions"

    if not image.local_path:
        raise RuntimeError("stored image local_path is required")

    mime_type = image.mime_type or "image/png"
    encoded = base64.b64encode(open(image.local_path, "rb").read()).decode("utf-8")
    prompt = (
        "你是OCR引擎。请仅提取图片中的可见文字并返回严格JSON。"
        "输出格式:{\"ocr_text\":\"...\",\"blocks\":[{\"text\":\"...\",\"confidence\":0.0,\"bbox\":[0,0,0,0]}],\"confidence\":0.0}。"
        "无法识别时保持空字符串，不要臆造。"
    )
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "你是严谨的OCR提字引擎。"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                ],
            },
        ],
    }
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
    except (error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"vision llm request failed: {exc}") from exc

    body = json.loads(raw)
    content = body["choices"][0]["message"]["content"].strip()
    parsed = safe_json_loads(content, "multimodal_ocr_vision")
    if parsed is None:
        raise RuntimeError("vision llm OCR JSON parse failed")

    blocks = [
        OCRBlock(
            text=str(item.get("text", "")).strip(),
            confidence=float(item.get("confidence", 0.0) or 0.0),
            bbox=item.get("bbox"),
        )
        for item in parsed.get("blocks", [])
        if str(item.get("text", "")).strip()
    ]
    return ImageOCRResult(
        file_id=image.file_id,
        source_url=image.public_url,
        ocr_text=str(parsed.get("ocr_text", "")).strip(),
        blocks=blocks,
        confidence=float(parsed.get("confidence", 0.0) or 0.0),
        extraction_source="vision_llm",
        status="success",
        error_message=None,
    )
