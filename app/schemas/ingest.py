from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.detect import StrategyConfig


class ImageInput(BaseModel):
    url: str | None = Field(default=None, description="图片 URL")
    base64: str | None = Field(default=None, description="Base64 图片数据")
    mime_type: str = Field(default="image/jpeg", description="图片 MIME 类型")

    @field_validator("mime_type")
    @classmethod
    def _validate_mime_type(cls, value: str) -> str:
        text = (value or "").strip().lower()
        if text in {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}:
            return "image/jpeg" if text == "image/jpg" else text
        return "image/jpeg"


class ImageAnalysisResult(BaseModel):
    image_index: int = Field(ge=0, description="图片序号")
    ocr_text: str = Field(default="", description="OCR 提取文字")
    scene_description: str = Field(default="", description="画面语义描述")
    key_entities: list[str] = Field(default_factory=list, description="关键实体")
    suspicious_signals: list[str] = Field(default_factory=list, description="可疑信号")
    source_platform: str = Field(default="", description="来源平台")


class MediaMeta(BaseModel):
    input_modalities: list[str] = Field(default_factory=lambda: ["text"])
    image_count: int = Field(default=0, ge=0)
    image_analyses: list[ImageAnalysisResult] = Field(default_factory=list)
    source_url: str | None = None
    source_title: str | None = None
    source_publish_date: str | None = None
    fusion_text: str = Field(default="")


class MultimodalDetectRequest(BaseModel):
    text: str = Field(default="", description="文本输入，可为空")
    images: list[ImageInput] = Field(default_factory=list, max_length=5)
    url: str | None = Field(default=None, description="新闻 URL")
    force: bool = Field(default=False, description="是否强制继续检测")

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return (value or "").strip()


class MultimodalDetectResponse(BaseModel):
    label: str
    confidence: float
    score: int
    reasons: list[str]
    strategy: StrategyConfig | None = None
    truncated: bool = False
    media_meta: MediaMeta | None = None
