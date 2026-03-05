from __future__ import annotations

from app.core.logger import get_logger
from app.schemas.ingest import MediaMeta, MultimodalDetectRequest
from app.services.ingestion.media_fusion import fuse_multimodal
from app.services.ingestion.vision_parser import parse_images
from app.services.news_crawler import crawl_news_url

logger = get_logger("truthcast.ingestion")


def ingest_multimodal(payload: MultimodalDetectRequest) -> tuple[str, MediaMeta]:
    text = (payload.text or "").strip()
    source_url = payload.url
    source_title: str | None = None
    source_publish_date: str | None = None

    if payload.url and not text:
        logger.info("多模态接入：检测到 URL，开始抓取新闻正文")
        crawled = crawl_news_url(payload.url)
        if crawled.success and crawled.content:
            text = crawled.content
            source_title = crawled.title
            source_publish_date = crawled.publish_date
        else:
            logger.warning(
                "多模态接入：URL 抓取失败，将继续处理其他输入。error=%s",
                crawled.error_msg,
            )

    image_analyses = parse_images(payload.images)
    fusion_text, media_meta = fuse_multimodal(
        text=text,
        image_analyses=image_analyses,
        source_url=source_url,
        source_title=source_title,
        source_publish_date=source_publish_date,
    )
    return fusion_text, media_meta
