from app.schemas.ingest import ImageAnalysisResult
from app.services.ingestion.media_fusion import fuse_multimodal


def test_fuse_multimodal_text_and_image() -> None:
    text, meta = fuse_multimodal(
        text="这是一段新闻文本",
        image_analyses=[
            ImageAnalysisResult(
                image_index=0,
                ocr_text="网传消息",
                scene_description="一张社交平台截图",
                key_entities=["某机构"],
                suspicious_signals=["时间戳模糊"],
                source_platform="微博",
            )
        ],
    )
    assert "这是一段新闻文本" in text
    assert "图片1" in text
    assert "网传消息" in text
    assert meta.image_count == 1
    assert "text" in meta.input_modalities
    assert "image" in meta.input_modalities


def test_fuse_multimodal_with_url_metadata() -> None:
    text, meta = fuse_multimodal(
        text="",
        source_url="https://example.com/news/1",
        source_title="示例新闻",
        source_publish_date="2026-03-04",
    )
    assert "来源链接：https://example.com/news/1" in text
    assert "来源标题：示例新闻" in text
    assert "来源发布日期：2026-03-04" in text
    assert "url" in meta.input_modalities


def test_fuse_multimodal_empty_input() -> None:
    text, meta = fuse_multimodal()
    assert text == "[无有效输入内容]"
    assert meta.input_modalities == ["text"]
    assert meta.image_count == 0
