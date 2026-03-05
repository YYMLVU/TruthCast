from __future__ import annotations

from app.core.logger import get_logger
from app.schemas.ingest import ImageAnalysisResult, MediaMeta

logger = get_logger("truthcast.media_fusion")


def fuse_multimodal(
    *,
    text: str = "",
    image_analyses: list[ImageAnalysisResult] | None = None,
    source_url: str | None = None,
    source_title: str | None = None,
    source_publish_date: str | None = None,
) -> tuple[str, MediaMeta]:
    sections: list[str] = []
    modalities: list[str] = []

    text_clean = (text or "").strip()
    analyses = image_analyses or []

    if text_clean:
        modalities.append("text")
        sections.append(text_clean)

    if source_url:
        modalities.append("url")
        url_lines = [f"来源链接：{source_url}"]
        if source_title:
            url_lines.append(f"来源标题：{source_title}")
        if source_publish_date:
            url_lines.append(f"来源发布日期：{source_publish_date}")
        sections.append("\n".join(url_lines))

    if analyses:
        modalities.append("image")
        for analysis in analyses:
            lines = [f"图片{analysis.image_index + 1}："]
            if analysis.ocr_text:
                lines.append(f"- 文字内容：{analysis.ocr_text}")
            if analysis.scene_description:
                lines.append(f"- 画面描述：{analysis.scene_description}")
            if analysis.key_entities:
                lines.append(f"- 关键实体：{'、'.join(analysis.key_entities)}")
            if analysis.suspicious_signals:
                lines.append(f"- 可疑信号：{'；'.join(analysis.suspicious_signals)}")
            if analysis.source_platform:
                lines.append(f"- 来源平台：{analysis.source_platform}")
            sections.append("\n".join(lines))

    fusion_text = "\n\n".join(part for part in sections if part.strip())
    if not fusion_text:
        fusion_text = "[无有效输入内容]"

    if not modalities:
        modalities = ["text"]

    meta = MediaMeta(
        input_modalities=modalities,
        image_count=len(analyses),
        image_analyses=analyses,
        source_url=source_url,
        source_title=source_title,
        source_publish_date=source_publish_date,
        fusion_text=fusion_text,
    )
    logger.info(
        "多模态融合完成：modalities=%s image_count=%s length=%s",
        modalities,
        len(analyses),
        len(fusion_text),
    )
    return fusion_text, meta
