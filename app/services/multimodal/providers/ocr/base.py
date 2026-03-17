from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas.multimodal import ImageOCRResult, StoredImageRecord


class OCRProvider(Protocol):
    def extract(self, image: StoredImageRecord) -> ImageOCRResult:
        ...


@dataclass(frozen=True)
class OCRProviderSettings:
    provider: str
    fallback_provider: str
    timeout_sec: float
    max_retries: int
    retry_delay: float
    confidence_threshold: float
    fallback_threshold: float
    debug_enabled: bool
