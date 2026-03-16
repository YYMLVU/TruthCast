from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas.multimodal import ImageAnalysisResult, StoredImageRecord


class VisionProvider(Protocol):
    def analyze(self, image: StoredImageRecord, raw_text: str) -> ImageAnalysisResult:
        ...


@dataclass(frozen=True)
class VisionProviderSettings:
    provider: str
    timeout_sec: float
    max_retries: int
    retry_delay: float
    debug_enabled: bool
