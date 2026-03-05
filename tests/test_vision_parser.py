from unittest.mock import MagicMock, patch

from app.schemas.ingest import ImageInput
from app.services.ingestion import vision_parser


def test_parse_images_empty() -> None:
    assert vision_parser.parse_images([]) == []


def test_parse_images_fallback_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("TRUTHCAST_VISION_LLM_ENABLED", "false")
    outputs = vision_parser.parse_images([ImageInput(url="https://example.com/a.jpg")])
    assert len(outputs) == 1
    assert outputs[0].scene_description.startswith("[图片解析不可用")


def test_build_image_content_with_url(monkeypatch) -> None:
    monkeypatch.setenv("TRUTHCAST_VISION_DETAIL", "high")
    content = vision_parser._build_image_content(
        ImageInput(url="https://example.com/a.jpg")
    )
    assert content is not None
    assert content["type"] == "image_url"
    assert content["image_url"]["url"] == "https://example.com/a.jpg"
    assert content["image_url"]["detail"] == "high"


def test_build_image_content_with_base64(monkeypatch) -> None:
    monkeypatch.setenv("TRUTHCAST_VISION_DETAIL", "auto")
    content = vision_parser._build_image_content(
        ImageInput(base64="ZmFrZS1kYXRh", mime_type="image/png")
    )
    assert content is not None
    assert content["type"] == "image_url"
    assert content["image_url"]["url"].startswith("data:image/png;base64,")


def test_parse_images_respects_max_images(monkeypatch) -> None:
    monkeypatch.setenv("TRUTHCAST_VISION_LLM_ENABLED", "false")
    monkeypatch.setenv("TRUTHCAST_VISION_MAX_IMAGES", "1")
    outputs = vision_parser.parse_images(
        [
            ImageInput(url="https://example.com/1.jpg"),
            ImageInput(url="https://example.com/2.jpg"),
        ]
    )
    assert len(outputs) == 1


@patch("app.services.ingestion.vision_parser.httpx.Client")
def test_parse_images_success_with_mocked_llm(mock_httpx_client, monkeypatch) -> None:
    monkeypatch.setenv("TRUTHCAST_VISION_LLM_ENABLED", "true")
    monkeypatch.setenv("TRUTHCAST_VISION_LLM_API_KEY", "test-key")
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"ocr_text":"截图文字","scene_description":"画面为一张新闻截图","key_entities":["某平台"],"suspicious_signals":[],"source_platform":"微博"}'
                }
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_client.__enter__.return_value = mock_client
    mock_httpx_client.return_value = mock_client

    outputs = vision_parser.parse_images([ImageInput(url="https://example.com/a.jpg")])
    assert len(outputs) == 1
    assert outputs[0].ocr_text == "截图文字"
    assert outputs[0].source_platform == "微博"


@patch("app.services.ingestion.vision_parser.httpx.Client")
def test_llm_request_trace_records_full_prompt_when_enabled(
    mock_httpx_client, monkeypatch
) -> None:
    monkeypatch.setenv("TRUTHCAST_VISION_LLM_ENABLED", "true")
    monkeypatch.setenv("TRUTHCAST_VISION_LLM_API_KEY", "test-key")
    monkeypatch.setenv("TRUTHCAST_DEBUG_VISION_PROMPT", "true")

    records: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        vision_parser,
        "_record_vision_trace",
        lambda stage, payload: records.append((stage, payload)),
    )

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"ocr_text":"","scene_description":"","key_entities":[],"suspicious_signals":[],"source_platform":""}'
                }
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_client.__enter__.return_value = mock_client
    mock_httpx_client.return_value = mock_client

    vision_parser.parse_images([ImageInput(url="https://example.com/a.jpg")])
    request_payloads = [payload for stage, payload in records if stage == "llm_request"]
    assert len(request_payloads) == 1
    assert "system_prompt" in request_payloads[0]
    assert isinstance(request_payloads[0]["system_prompt"], str)
    assert request_payloads[0]["system_prompt"]


@patch("app.services.ingestion.vision_parser.httpx.Client")
def test_llm_request_trace_records_preview_when_full_prompt_disabled(
    mock_httpx_client, monkeypatch
) -> None:
    monkeypatch.setenv("TRUTHCAST_VISION_LLM_ENABLED", "true")
    monkeypatch.setenv("TRUTHCAST_VISION_LLM_API_KEY", "test-key")
    monkeypatch.setenv("TRUTHCAST_DEBUG_VISION_PROMPT", "false")

    records: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        vision_parser,
        "_record_vision_trace",
        lambda stage, payload: records.append((stage, payload)),
    )

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"ocr_text":"","scene_description":"","key_entities":[],"suspicious_signals":[],"source_platform":""}'
                }
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_client.__enter__.return_value = mock_client
    mock_httpx_client.return_value = mock_client

    vision_parser.parse_images([ImageInput(url="https://example.com/a.jpg")])
    request_payloads = [payload for stage, payload in records if stage == "llm_request"]
    assert len(request_payloads) == 1
    assert "system_prompt" not in request_payloads[0]
    assert "system_prompt_preview" in request_payloads[0]
