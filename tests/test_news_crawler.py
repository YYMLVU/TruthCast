import pytest
import httpx
from unittest.mock import MagicMock, patch
from app.services.news_crawler import (
    crawl_news_url,
    _preprocess_html,
    extract_related_image_urls,
)


def test_preprocess_html():
    html = """
    <html>
        <head><title>Ignore Me</title></head>
        <body>
            <nav>Menu</nav>
            <article>
                <h1>Real Title</h1>
                <p>Real content here.</p>
                <script>alert('bad');</script>
                <style>.ads { display: none; }</style>
            </article>
            <footer>Contact Us</footer>
            <!-- Secret comment -->
        </body>
    </html>
    """
    cleaned = _preprocess_html(html)
    assert "Real Title" in cleaned
    assert "Real content here" in cleaned
    assert "<script>" not in cleaned
    assert "<style>" not in cleaned
    assert "<nav>" not in cleaned
    assert "<footer>" not in cleaned
    assert "Secret comment" not in cleaned


@patch("app.services.news_crawler.httpx.Client")
def test_crawl_news_url_success(mock_httpx_client):
    # Mock HTTP response for website content
    mock_resp_web = MagicMock()
    mock_resp_web.text = "<html><body><h1>News</h1><p>Content</p></body></html>"
    mock_resp_web.status_code = 200
    mock_resp_web.raise_for_status = MagicMock()

    # Mock HTTP response for LLM API
    mock_resp_llm = MagicMock()
    mock_resp_llm.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"title": "News Title", "content": "News Body", "publish_date": "2024-02-24"}'
                }
            }
        ]
    }
    mock_resp_llm.status_code = 200
    mock_resp_llm.raise_for_status = MagicMock()

    mock_client_instance = MagicMock()
    # First call is GET (website), second is POST (LLM)
    mock_client_instance.get.return_value = mock_resp_web
    mock_client_instance.post.return_value = mock_resp_llm
    mock_client_instance.__enter__.return_value = mock_client_instance
    mock_httpx_client.return_value = mock_client_instance

    url = "https://example.com/news"
    # Ensure API Key is present for test
    with patch.dict("os.environ", {"TRUTHCAST_LLM_API_KEY": "test-key"}):
        result = crawl_news_url(url)

    assert result.success is True
    assert result.title == "News Title"
    assert result.content == "News Body"
    assert result.publish_date == "2024-02-24"
    assert result.source_url == url


@patch("app.services.news_crawler.httpx.Client")
def test_crawl_news_url_http_error(mock_httpx_client):
    mock_client_instance = MagicMock()
    mock_client_instance.get.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=MagicMock(), response=MagicMock()
    )
    mock_client_instance.__enter__.return_value = mock_client_instance
    mock_httpx_client.return_value = mock_client_instance

    url = "https://example.com/404"
    result = crawl_news_url(url)

    assert result.success is False
    assert "404" in result.error_msg
    assert result.source_url == url


@patch("app.services.news_crawler.httpx.Client")
def test_crawl_news_url_llm_error(mock_httpx_client):
    # Mock HTTP success for web
    mock_resp_web = MagicMock()
    mock_resp_web.text = "<html><body>Some News</body></html>"
    mock_resp_web.status_code = 200

    mock_client_instance = MagicMock()
    mock_client_instance.get.return_value = mock_resp_web
    # Mock LLM failure
    mock_client_instance.post.side_effect = Exception("LLM connection failed")
    mock_client_instance.__enter__.return_value = mock_client_instance
    mock_httpx_client.return_value = mock_client_instance

    url = "https://example.com/news"
    with patch.dict("os.environ", {"TRUTHCAST_LLM_API_KEY": "test-key"}):
        result = crawl_news_url(url)

    assert result.success is False
    assert "LLM extraction failed" in result.error_msg
    assert result.content == "[提取失败]"


def test_extract_related_image_urls_prefers_article_related_image() -> None:
    html = """
    <html><head>
      <meta property="og:image" content="https://cdn.example.com/news/main.jpg" />
    </head>
    <body>
      <header><img src="https://cdn.example.com/assets/logo.png" alt="网站logo"></header>
      <article class="news-content">
        <h1>某地发布灾害通告</h1>
        <img src="/images/disaster-scene.jpg" alt="某地灾害现场" width="1024" height="768" />
      </article>
      <aside><img src="https://cdn.example.com/ad/banner.jpg" alt="广告图"></aside>
    </body></html>
    """
    urls = extract_related_image_urls(
        page_url="https://news.example.com/a/1",
        html=html,
        context_text="某地发布灾害通告 灾害现场 图片",
    )
    assert "https://cdn.example.com/news/main.jpg" in urls
    assert "https://news.example.com/images/disaster-scene.jpg" in urls
    assert "https://cdn.example.com/ad/banner.jpg" not in urls


def test_extract_related_image_urls_filters_irrelevant_icons() -> None:
    html = """
    <html><body>
      <img src="/static/logo.svg" alt="logo" width="64" height="64" />
      <img src="/static/icon.png" alt="icon" width="32" height="32" />
      <img src="/gallery/news-photo.webp" alt="事故现场" width="800" height="500" />
    </body></html>
    """
    urls = extract_related_image_urls(
        page_url="https://news.example.com/detail/2",
        html=html,
        context_text="事故现场 实况 报道",
    )
    assert "https://news.example.com/gallery/news-photo.webp" in urls
    assert all("logo" not in u for u in urls)
    assert all("icon" not in u for u in urls)
