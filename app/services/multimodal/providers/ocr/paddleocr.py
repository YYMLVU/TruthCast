from __future__ import annotations

import json
import os
from urllib import error, request

from app.schemas.multimodal import ImageOCRResult, OCRBlock, StoredImageRecord
from app.services.json_utils import safe_json_loads


def extract_with_paddleocr(image: StoredImageRecord, timeout_sec: float) -> ImageOCRResult:
    base_url = os.getenv("TRUTHCAST_PADDLEOCR_BASE_URL", "").strip()
    if not base_url:
        raise RuntimeError("paddleocr base url is required")
    api_key = os.getenv("TRUTHCAST_PADDLEOCR_API_KEY", "").strip()
    if not image.local_path:
        raise RuntimeError("stored image local_path is required")

    payload = {"file_id": image.file_id, "image_path": image.local_path, "public_url": image.public_url}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = request.Request(
        base_url.rstrip("/") + "/ocr",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
    except (error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"paddleocr request failed: {exc}") from exc

    parsed = safe_json_loads(raw, "multimodal_ocr_paddle")
    if parsed is None:
        raise RuntimeError("paddleocr JSON parse failed")
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
        extraction_source="paddleocr",
        status=str(parsed.get("status", "success") or "success"),
        error_message=parsed.get("error_message"),
    )
