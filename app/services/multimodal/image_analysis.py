from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.core.logger import get_logger
from app.schemas.multimodal import ImageAnalysisResult, StoredImageRecord
from app.services.json_utils import serialize_for_json
from app.services.multimodal.providers.vision.base import VisionProviderSettings
from app.services.multimodal.providers.vision.vision_llm import analyze_with_vision_llm


logger = get_logger("truthcast.multimodal.vision")


def _settings() -> VisionProviderSettings:
    return VisionProviderSettings(
        provider=os.getenv("TRUTHCAST_VISION_PROVIDER", "vision_llm").strip().lower()
        or "vision_llm",
        timeout_sec=float(
            os.getenv("TRUTHCAST_VISION_TIMEOUT_SEC", "20").strip() or 20
        ),
        max_retries=int(os.getenv("TRUTHCAST_VISION_MAX_RETRIES", "1").strip() or 1),
        retry_delay=float(os.getenv("TRUTHCAST_VISION_RETRY_DELAY", "1").strip() or 1),
        debug_enabled=os.getenv("TRUTHCAST_DEBUG_VISION", "true").strip().lower()
        == "true",
    )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _record_vision_trace(stage: str, payload: dict) -> None:
    if not _settings().debug_enabled:
        return
    debug_dir = _project_root() / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    trace_file = debug_dir / "multimodal_vision_trace.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "payload": serialize_for_json(payload),
    }
    with trace_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _analyze_with_vision_llm(
    image: StoredImageRecord, raw_text: str
) -> ImageAnalysisResult:
    return analyze_with_vision_llm(image, raw_text, timeout_sec=_settings().timeout_sec)


def _normalize_result(
    result: ImageAnalysisResult | dict, image: StoredImageRecord
) -> ImageAnalysisResult:
    if isinstance(result, ImageAnalysisResult):
        return result
    payload = dict(result)
    payload.setdefault("file_id", image.file_id)
    payload.setdefault("source_url", image.public_url)
    payload.setdefault("key_elements", [])
    payload.setdefault("matched_claims", [])
    payload.setdefault("semantic_conflicts", [])
    payload.setdefault("status", "success")
    payload.setdefault("error_message", None)
    return ImageAnalysisResult.model_validate(payload)


def _call_provider(
    fn: Callable[[StoredImageRecord, str], ImageAnalysisResult | dict],
    image: StoredImageRecord,
    raw_text: str,
    retries: int,
    retry_delay: float,
) -> ImageAnalysisResult:
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            return _normalize_result(fn(image, raw_text), image)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            _record_vision_trace(
                "provider_error",
                {
                    "provider": "vision_llm",
                    "file_id": image.file_id,
                    "attempt": attempt + 1,
                    "error": str(exc),
                },
            )
            if attempt < max(1, retries) - 1:
                time.sleep(retry_delay)
    if last_error is not None:
        raise last_error
    raise RuntimeError("vision provider failed without explicit error")


def analyze_image(image: StoredImageRecord, raw_text: str) -> ImageAnalysisResult:
    settings = _settings()
    provider_name = settings.provider or "vision_llm"
    logger.info(
        "图像分析：开始分析，provider=%s, file_id=%s",
        provider_name,
        image.file_id,
    )
    _record_vision_trace(
        "input",
        {
            "provider": provider_name,
            "file_id": image.file_id,
            "timeout_sec": settings.timeout_sec,
            "max_retries": settings.max_retries,
        },
    )
    _record_vision_trace(
        "provider_selected", {"provider": provider_name, "file_id": image.file_id}
    )
    if provider_name != "vision_llm":
        logger.warning(
            "图像分析：不支持的provider，provider=%s, file_id=%s",
            provider_name,
            image.file_id,
        )
        raise RuntimeError(f"unsupported vision provider: {provider_name}")
    _record_vision_trace(
        "provider_request",
        {
            "provider": provider_name,
            "file_id": image.file_id,
            "raw_text_preview": raw_text[:120],
        },
    )
    try:
        result = _call_provider(
            _analyze_with_vision_llm,
            image,
            raw_text,
            settings.max_retries,
            settings.retry_delay,
        )
    except Exception as exc:
        logger.warning(
            "图像分析：provider调用失败，provider=%s, file_id=%s, error=%s",
            provider_name,
            image.file_id,
            exc,
        )
        raise
    _record_vision_trace(
        "provider_response",
        {
            "provider": provider_name,
            "file_id": image.file_id,
            "status": result.status,
            "relevance_score": result.relevance_score,
        },
    )
    _record_vision_trace(
        "output",
        {
            "provider": provider_name,
            "file_id": image.file_id,
            "summary": result.image_summary,
            "status": result.status,
        },
    )
    logger.info(
        "图像分析：分析成功，provider=%s, relevance=%s, conflicts=%s, file_id=%s",
        provider_name,
        result.relevance_score,
        len(result.semantic_conflicts),
        image.file_id,
    )
    return result
