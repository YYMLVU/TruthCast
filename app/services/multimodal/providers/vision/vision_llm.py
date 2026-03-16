from __future__ import annotations

import base64
import json
import os
from urllib import error, request

from app.schemas.multimodal import ImageAnalysisResult, StoredImageRecord
from app.services.json_utils import safe_json_loads


def analyze_with_vision_llm(image: StoredImageRecord, raw_text: str, timeout_sec: float) -> ImageAnalysisResult:
    api_key = os.getenv("TRUTHCAST_VISION_API_KEY", os.getenv("TRUTHCAST_LLM_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("vision api key is required")

    base_url = os.getenv("TRUTHCAST_VISION_BASE_URL", os.getenv("TRUTHCAST_LLM_BASE_URL", "https://api.openai.com/v1")).strip()
    model = os.getenv("TRUTHCAST_VISION_MODEL", os.getenv("TRUTHCAST_LLM_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    endpoint = base_url.rstrip("/") + "/chat/completions"

    if not image.local_path:
        raise RuntimeError("stored image local_path is required")

    encoded = base64.b64encode(open(image.local_path, "rb").read()).decode("utf-8")
    prompt = (
        "你是新闻图片分析引擎。请结合给定新闻文本分析图片，并只返回严格JSON。"
        "输出结构:{\"image_summary\":\"...\",\"relevance_score\":0,\"relevance_reason\":\"...\",\"key_elements\":[],\"matched_claims\":[],\"semantic_conflicts\":[],\"image_credibility_label\":\"supportive|suspicious|uncertain\",\"image_credibility_score\":0}。"
    )
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "你是严谨的新闻图片分析助手。"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{prompt}\n\n新闻文本:\n{raw_text}"},
                    {"type": "image_url", "image_url": {"url": f"data:{image.mime_type};base64,{encoded}"}},
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
        raise RuntimeError(f"vision analysis request failed: {exc}") from exc

    body = json.loads(raw)
    content = body["choices"][0]["message"]["content"].strip()
    parsed = safe_json_loads(content, "multimodal_vision")
    if parsed is None:
        raise RuntimeError("vision analysis JSON parse failed")
    parsed.setdefault("file_id", image.file_id)
    parsed.setdefault("source_url", image.public_url)
    parsed.setdefault("status", "success")
    parsed.setdefault("error_message", None)
    return ImageAnalysisResult.model_validate(parsed)
