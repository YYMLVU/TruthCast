from app.services.url_extraction.publishers.ckxxapp import (
    PublisherArticleResult,
    try_extract_ckxxapp_article,
)


def try_extract_publisher_article(source_url: str, html: str) -> PublisherArticleResult | None:
    return try_extract_ckxxapp_article(source_url, html)
