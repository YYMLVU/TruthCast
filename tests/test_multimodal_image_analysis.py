import json
from pathlib import Path

import pytest

from app.schemas.multimodal import StoredImageRecord
from app.services.multimodal import image_analysis as vision_service


def _stored_image(tmp_path: Path) -> StoredImageRecord:
    image_path = tmp_path / "poster.png"
    image_path.write_bytes(b"fake-image-bytes")
    return StoredImageRecord(
        file_id="img_abcdef123456",
        filename="poster.png",
        mime_type="image/png",
        size=len(b"fake-image-bytes"),
        public_url="/multimodal/files/img_abcdef123456",
        local_path=str(image_path),
    )


def test_analyze_image_uses_vision_provider_and_returns_structured_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRUTHCAST_VISION_PROVIDER", "vision_llm")

    def fake_provider(_: StoredImageRecord, raw_text: str):
        assert raw_text == "原始新闻文本"
        return {
            "image_summary": "图片显示一份通知截图",
            "relevance_score": 88,
            "relevance_reason": "与输入新闻内容高度相关",
            "key_elements": ["通知", "机构名称"],
            "matched_claims": ["主张1"],
            "semantic_conflicts": [],
            "image_credibility_label": "supportive",
            "image_credibility_score": 80,
            "status": "success",
            "error_message": None,
        }

    monkeypatch.setattr(
        vision_service, "_analyze_with_vision_llm", fake_provider, raising=False
    )

    result = vision_service.analyze_image(_stored_image(tmp_path), "原始新闻文本")

    assert result.image_summary == "图片显示一份通知截图"
    assert result.relevance_score == 88
    assert result.file_id == "img_abcdef123456"


def test_analyze_image_writes_vision_trace_when_debug_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRUTHCAST_VISION_PROVIDER", "vision_llm")
    monkeypatch.setenv("TRUTHCAST_DEBUG_VISION", "true")

    debug_dir = tmp_path / "debug"
    debug_dir.mkdir()
    monkeypatch.setattr(
        vision_service, "_project_root", lambda: tmp_path, raising=False
    )

    def fake_provider(_: StoredImageRecord, __: str):
        return {
            "image_summary": "图片显示一份通知截图",
            "relevance_score": 88,
            "relevance_reason": "与输入新闻内容高度相关",
            "key_elements": ["通知"],
            "matched_claims": [],
            "semantic_conflicts": [],
            "image_credibility_label": "supportive",
            "image_credibility_score": 80,
            "status": "success",
            "error_message": None,
        }

    monkeypatch.setattr(
        vision_service, "_analyze_with_vision_llm", fake_provider, raising=False
    )

    vision_service.analyze_image(_stored_image(tmp_path), "原始新闻文本")

    trace_file = debug_dir / "multimodal_vision_trace.jsonl"
    assert trace_file.exists()
    content = trace_file.read_text(encoding="utf-8").strip().splitlines()
    stages = [json.loads(line)["stage"] for line in content]
    assert "provider_selected" in stages
    assert "output" in stages
