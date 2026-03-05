import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from app.core.logger import get_logger
from app.services.json_utils import safe_json_loads

logger = get_logger("truthcast.news_crawler")


@dataclass
class CrawledNews:
    title: str
    content: str
    publish_date: str
    source_url: str
    image_urls: list[str] = field(default_factory=list)
    success: bool = True
    error_msg: str = ""


def crawl_news_url(url: str, timeout_sec: float = 15.0) -> CrawledNews:
    """
    抓取新闻 URL 并提取核心内容 (标题, 正文, 发布日期)
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        with httpx.Client(
            timeout=timeout_sec, follow_redirects=True, headers=headers
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text

        # 1. 简单清洗 HTML 减少 token 消耗
        cleaned_html = _preprocess_html(html)

        # 2. 调用 LLM 进行结构化提取
        extracted = _extract_news_with_llm(url, cleaned_html)
        if not extracted.success:
            return extracted

        context_text = f"{extracted.title} {extracted.content}".strip()
        related_images = extract_related_image_urls(
            page_url=url,
            html=html,
            context_text=context_text,
        )
        extracted.image_urls = related_images
        return extracted

    except Exception as exc:
        logger.error("抓取 URL 失败: url=%s, error=%s", url, exc)
        return CrawledNews(
            title="",
            content="",
            publish_date="",
            source_url=url,
            image_urls=[],
            success=False,
            error_msg=str(exc),
        )


_NEGATIVE_IMAGE_HINTS = {
    "logo",
    "icon",
    "avatar",
    "sprite",
    "banner",
    "ad",
    "ads",
    "promo",
    "qrcode",
    "qr",
    "placeholder",
    "thumb",
}

_POSITIVE_CONTAINER_HINTS = {
    "article",
    "content",
    "post",
    "main",
    "story",
    "detail",
    "news",
}


def extract_related_image_urls(
    page_url: str, html: str, context_text: str
) -> list[str]:
    candidates: list[dict[str, Any]] = []

    og_match = re.search(
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )
    if og_match:
        og_url = _normalize_image_url(page_url, og_match.group(1).strip())
        if og_url:
            candidates.append(
                {
                    "url": og_url,
                    "score": 120,
                    "reason": ["meta:og_image"],
                    "alt": "",
                    "width": None,
                    "height": None,
                }
            )

    for img_tag in re.findall(r"<img\b[^>]*>", html, flags=re.IGNORECASE):
        attrs = _parse_tag_attrs(img_tag)
        src_raw = (
            attrs.get("src")
            or attrs.get("data-src")
            or attrs.get("data-original")
            or attrs.get("data-lazy-src")
            or ""
        ).strip()
        if not src_raw:
            continue
        url = _normalize_image_url(page_url, src_raw)
        if not url:
            continue
        alt = (attrs.get("alt") or attrs.get("title") or "").strip()
        width = _safe_int(attrs.get("width"))
        height = _safe_int(attrs.get("height"))

        score, reasons = _score_image_candidate(
            url=url,
            alt_text=alt,
            width=width,
            height=height,
            context_text=context_text,
            tag_text=img_tag,
        )
        candidates.append(
            {
                "url": url,
                "score": score,
                "reason": reasons,
                "alt": alt,
                "width": width,
                "height": height,
            }
        )

    best_by_url: dict[str, dict[str, Any]] = {}
    for item in candidates:
        old = best_by_url.get(item["url"])
        if old is None or item["score"] > old["score"]:
            best_by_url[item["url"]] = item

    min_score = _image_min_score()
    topk = _image_max_items()
    ranked = sorted(best_by_url.values(), key=lambda x: float(x["score"]), reverse=True)
    filtered = [x for x in ranked if float(x["score"]) >= min_score][:topk]

    if _crawler_debug_images_enabled():
        logger.info(
            "Crawler 图片筛选: total=%d kept=%d min_score=%.1f topk=%d",
            len(ranked),
            len(filtered),
            min_score,
            topk,
        )
        for item in filtered:
            logger.info(
                "Crawler 图片入选: score=%.1f url=%s reasons=%s",
                float(item["score"]),
                item["url"],
                ",".join(item["reason"]),
            )

    return [str(item["url"]) for item in filtered]


def _score_image_candidate(
    *,
    url: str,
    alt_text: str,
    width: int | None,
    height: int | None,
    context_text: str,
    tag_text: str,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    lower_url = url.lower()
    lower_tag = tag_text.lower()
    lower_alt = alt_text.lower()

    if any(token in lower_url for token in _NEGATIVE_IMAGE_HINTS):
        score -= 80
        reasons.append("negative:url_hint")

    if any(token in lower_tag for token in _POSITIVE_CONTAINER_HINTS):
        score += 25
        reasons.append("positive:container_hint")

    if lower_url.endswith((".jpg", ".jpeg", ".png", ".webp")):
        score += 12
        reasons.append("positive:image_ext")
    if lower_url.endswith(".svg"):
        score -= 50
        reasons.append("negative:svg")
    if lower_url.endswith(".gif"):
        score -= 20
        reasons.append("negative:gif")

    if width is not None and height is not None:
        if min(width, height) < 120:
            score -= 35
            reasons.append("negative:tiny_size")
        else:
            score += 8
            reasons.append("positive:size_ok")
    elif width is not None or height is not None:
        score -= 5
        reasons.append("negative:partial_size")

    overlap = _keyword_overlap_score(context_text=context_text, alt_text=alt_text)
    if overlap > 0:
        score += min(40, overlap * 10)
        reasons.append("positive:context_overlap")

    if not reasons:
        reasons.append("neutral:no_strong_signal")
    return score, reasons


def _keyword_overlap_score(context_text: str, alt_text: str) -> int:
    if not context_text or not alt_text:
        return 0
    context_tokens = set(_tokenize_context(context_text))
    alt_tokens = set(_tokenize_context(alt_text))
    if not context_tokens or not alt_tokens:
        return 0
    return len(context_tokens & alt_tokens)


def _tokenize_context(text: str) -> list[str]:
    chunks = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{4,}", text)
    out: list[str] = []
    for c in chunks:
        t = c.strip().lower()
        if not t:
            continue
        out.append(t)
    return out


def _parse_tag_attrs(tag_html: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key, v1, v2, v3 in re.findall(
        r"([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))",
        tag_html,
    ):
        value = v1 or v2 or v3
        attrs[key.lower()] = value
    return attrs


def _normalize_image_url(page_url: str, raw_url: str) -> str | None:
    value = (raw_url or "").strip()
    if not value:
        return None
    if value.startswith("//"):
        value = "https:" + value
    norm = urljoin(page_url, value)
    parsed = urlparse(norm)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return norm


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    m = re.search(r"\d+", str(value))
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def _image_max_items() -> int:
    raw = os.getenv("TRUTHCAST_CRAWLER_IMAGE_MAX_ITEMS", "3").strip()
    try:
        value = int(raw)
    except ValueError:
        return 3
    return max(1, min(10, value))


def _image_min_score() -> float:
    raw = os.getenv("TRUTHCAST_CRAWLER_IMAGE_MIN_SCORE", "10").strip()
    try:
        value = float(raw)
    except ValueError:
        return 10.0
    return max(-50.0, min(100.0, value))


def _crawler_debug_images_enabled() -> bool:
    return (
        os.getenv("TRUTHCAST_DEBUG_CRAWLER_IMAGES", "false").strip().lower() == "true"
    )


def _preprocess_html(html: str) -> str:
    """
    移除脚本、样式、注释等，只保留主体内容块
    """
    # 移除 script, style, head, nav, footer, iframe
    html = re.sub(
        r"<(script|style|head|nav|footer|iframe)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # 移除注释
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # 移除多余空白
    html = re.sub(r"\s+", " ", html).strip()
    # 截断太长的内容 (例如保留前 15000 字符，通常够了)
    return html[:15000]


def _extract_news_with_llm(url: str, html: str) -> CrawledNews:
    """
    利用 LLM 从清洗后的 HTML 中提取新闻要素
    """
    api_key = os.getenv("TRUTHCAST_LLM_API_KEY", "").strip()
    if not api_key:
        logger.warning("Crawler: TRUTHCAST_LLM_API_KEY 为空，跳过 LLM 提取")
        return CrawledNews(
            title="",
            content="[未配置 API Key]",
            publish_date="",
            source_url=url,
            success=False,
        )

    base_url = os.getenv("TRUTHCAST_LLM_BASE_URL", "https://api.openai.com/v1").rstrip(
        "/"
    )
    model = os.getenv("TRUTHCAST_CRAWLER_LLM_MODEL") or os.getenv(
        "TRUTHCAST_LLM_MODEL", "gpt-4o-mini"
    )

    system_prompt = """你是一个专业的新闻内容提取助手。你的任务是从给定的 HTML 源码片段中准确提取新闻的核心信息。
请输出合法的 JSON 格式，包含以下字段：
- title: 新闻标题
- content: 新闻正文内容（保持段落完整，移除广告、推荐阅读等干扰信息）
- publish_date: 发布日期（格式：YYYY-MM-DD，如果无法确定则留空）

注意：如果 HTML 中包含多篇新闻或无关信息，请只提取最主要的那篇新闻。
"""
    user_prompt = f"URL: {url}\n\nHTML Snippet:\n{html}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"]

        parsed = safe_json_loads(raw_content)
        if not isinstance(parsed, dict):
            raise ValueError("crawler llm response is not valid JSON object")
        res_data: dict[str, Any] = parsed

        return CrawledNews(
            title=str(res_data.get("title", "")).strip(),
            content=str(res_data.get("content", "")).strip(),
            publish_date=str(res_data.get("publish_date", "")).strip(),
            source_url=url,
            success=True,
        )
    except Exception as exc:
        logger.error("LLM 提取新闻内容失败: %s", exc)
        return CrawledNews(
            title="",
            content="[提取失败]",
            publish_date="",
            source_url=url,
            success=False,
            error_msg=f"LLM extraction failed: {exc}",
        )
