from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.logger import get_logger
from app.schemas.ingest import ImageAnalysisResult, ImageInput
from app.services.json_utils import safe_json_loads, serialize_for_json

logger = get_logger("truthcast.vision_parser")


def parse_images(images: list[ImageInput]) -> list[ImageAnalysisResult]:
    if not images:
        return []

    limited_images = images[: _max_images()]
    if not _vision_enabled():
        logger.info("图片解析：TRUTHCAST_VISION_LLM_ENABLED 未启用，使用兜底结果")
        return [_fallback_analysis(idx) for idx in range(len(limited_images))]

    api_key = _vision_api_key()
    if not api_key:
        logger.warning("图片解析：TRUTHCAST_VISION_LLM_API_KEY 为空，使用兜底结果")
        return [_fallback_analysis(idx) for idx in range(len(limited_images))]

    outputs: list[ImageAnalysisResult] = []
    for idx, image in enumerate(limited_images):
        _record_vision_trace(
            "input",
            {
                "image_index": idx,
                "has_url": bool(image.url),
                "has_base64": bool(image.base64),
                "mime_type": image.mime_type,
            },
        )
        try:
            outputs.append(
                _analyze_single_image(image=image, image_index=idx, api_key=api_key)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "图片解析：第 %s 张图片解析失败，回退兜底。error=%s", idx + 1, exc
            )
            _record_vision_trace("llm_error", {"image_index": idx, "error": str(exc)})
            outputs.append(_fallback_analysis(idx))
    return outputs


def _analyze_single_image(
    *, image: ImageInput, image_index: int, api_key: str
) -> ImageAnalysisResult:
    image_content = _build_image_content(image)
    if image_content is None:
        return _fallback_analysis(image_index)

    base_url = _vision_base_url()
    model = _vision_model()
    endpoint = base_url.rstrip("/") + "/chat/completions"

    system_prompt = (
        "你是新闻图片事实核查助手。请解析图片并严格输出 JSON。"
        "输出字段："
        "ocr_text、scene_description、key_entities、suspicious_signals、source_platform。"
        "要求："
        "1) ocr_text 提取图片可见文字；"
        "2) scene_description 客观描述画面；"
        "3) key_entities 只保留可识别实体；"
        "4) suspicious_signals 仅记录可疑线索；"
        "5) 输出必须为合法 JSON，不要 Markdown。"
    )
    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请分析这张图片。"},
                    image_content,
                ],
            },
        ],
    }

    trace_request_payload: dict[str, Any] = {
        "image_index": image_index,
        "model": model,
        "base_url": base_url,
        "detail": _vision_detail(),
        "endpoint": endpoint,
    }
    if _vision_prompt_trace_enabled():
        trace_request_payload["system_prompt"] = system_prompt
    else:
        trace_request_payload["system_prompt_preview"] = system_prompt[:200]

    _record_vision_trace(
        "llm_request",
        trace_request_payload,
    )

    with httpx.Client(timeout=_vision_timeout_sec()) as client:
        resp = client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    raw_content = data["choices"][0]["message"]["content"]

    _record_vision_trace(
        "llm_response",
        {
            "image_index": image_index,
            "raw_content": str(raw_content)[:1000],
        },
    )

    parsed = safe_json_loads(str(raw_content), "vision_parser")
    if parsed is None:
        return _fallback_analysis(image_index)

    result = ImageAnalysisResult(
        image_index=image_index,
        ocr_text=str(parsed.get("ocr_text", "")).strip(),
        scene_description=str(parsed.get("scene_description", "")).strip(),
        key_entities=_as_str_list(parsed.get("key_entities", [])),
        suspicious_signals=_as_str_list(parsed.get("suspicious_signals", [])),
        source_platform=str(parsed.get("source_platform", "")).strip(),
    )
    _record_vision_trace("output", result.model_dump())
    return result


def _build_image_content(image: ImageInput) -> dict[str, Any] | None:
    detail = _vision_detail()
    if image.url:
        return {
            "type": "image_url",
            "image_url": {
                "url": image.url,
                "detail": detail,
            },
        }
    if image.base64:
        data_url = f"data:{image.mime_type};base64,{image.base64}"
        return {
            "type": "image_url",
            "image_url": {
                "url": data_url,
                "detail": detail,
            },
        }
    return None


def _fallback_analysis(image_index: int) -> ImageAnalysisResult:
    return ImageAnalysisResult(
        image_index=image_index,
        ocr_text="",
        scene_description="[图片解析不可用，未提取画面信息]",
        key_entities=[],
        suspicious_signals=[],
        source_platform="",
    )


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _vision_enabled() -> bool:
    return os.getenv("TRUTHCAST_VISION_LLM_ENABLED", "false").strip().lower() == "true"


def _vision_api_key() -> str:
    return (
        os.getenv("TRUTHCAST_VISION_LLM_API_KEY", "").strip()
        or os.getenv("TRUTHCAST_LLM_API_KEY", "").strip()
    )


def _vision_base_url() -> str:
    return (
        os.getenv("TRUTHCAST_VISION_LLM_BASE_URL", "").strip()
        or os.getenv("TRUTHCAST_LLM_BASE_URL", "https://api.openai.com/v1").strip()
    )


def _vision_model() -> str:
    return (
        os.getenv("TRUTHCAST_VISION_LLM_MODEL", "").strip()
        or os.getenv("TRUTHCAST_LLM_MODEL", "gpt-4o-mini").strip()
    )


def _vision_timeout_sec() -> float:
    raw = os.getenv("TRUTHCAST_VISION_TIMEOUT_SEC", "30").strip()
    try:
        value = float(raw)
    except ValueError:
        return 30.0
    return max(5.0, min(120.0, value))


def _vision_detail() -> str:
    value = os.getenv("TRUTHCAST_VISION_DETAIL", "auto").strip().lower()
    if value not in {"low", "high", "auto"}:
        return "auto"
    return value


def _max_images() -> int:
    raw = os.getenv("TRUTHCAST_VISION_MAX_IMAGES", "5").strip()
    try:
        value = int(raw)
    except ValueError:
        return 5
    return max(1, min(10, value))


def _vision_prompt_trace_enabled() -> bool:
    return os.getenv("TRUTHCAST_DEBUG_VISION_PROMPT", "false").strip().lower() == "true"


def _record_vision_trace(stage: str, payload: dict[str, Any]) -> None:
    if os.getenv("TRUTHCAST_DEBUG_VISION", "false").strip().lower() != "true":
        return
    try:
        project_root = Path(__file__).resolve().parents[3]
        debug_dir = project_root / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        trace_file = debug_dir / "vision_trace.jsonl"
        item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "payload": serialize_for_json(payload),
        }
        with trace_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        return
