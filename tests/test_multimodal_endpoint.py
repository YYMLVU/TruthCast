from fastapi.testclient import TestClient

from app.main import app
from app.schemas.detect import StrategyConfig
from app.schemas.ingest import ImageAnalysisResult, MediaMeta
from app.services.text_complexity import ScoreResult


def test_multimodal_endpoint_empty_input_returns_needs_context() -> None:
    client = TestClient(app)
    response = client.post("/detect/multimodal", json={})
    body = response.json()
    assert response.status_code == 200
    assert body["label"] == "needs_context"
    assert body["score"] == 50


def test_multimodal_endpoint_success_and_append_image_signals(monkeypatch) -> None:
    from app.api import routes_detect

    def _mock_ingest(payload):
        meta = MediaMeta(
            input_modalities=["text", "image"],
            image_count=1,
            image_analyses=[
                ImageAnalysisResult(
                    image_index=0,
                    ocr_text="截图中的文字",
                    scene_description="截图展示某条传言",
                    suspicious_signals=["图片边缘存在拼接痕迹"],
                )
            ],
            fusion_text="融合文本",
        )
        return "融合文本", meta

    def _mock_detect(text: str, force: bool = False, enable_news_gate: bool = False):
        return ScoreResult(
            label="suspicious",
            confidence=0.81,
            score=62,
            reasons=["文本存在未经证实陈述"],
            strategy=StrategyConfig(),
        )

    monkeypatch.setattr(routes_detect, "ingest_multimodal", _mock_ingest)
    monkeypatch.setattr(routes_detect, "detect_risk_snapshot", _mock_detect)

    client = TestClient(app)
    response = client.post(
        "/detect/multimodal",
        json={
            "text": "请分析这条新闻",
            "images": [{"url": "https://example.com/a.jpg"}],
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["label"] == "suspicious"
    assert any("图片1可疑信号" in reason for reason in body["reasons"])


def test_multimodal_endpoint_truncated(monkeypatch) -> None:
    from app.api import routes_detect

    def _mock_ingest(payload):
        meta = MediaMeta(input_modalities=["text"], image_count=0, fusion_text="x" * 50)
        return "x" * 50, meta

    def _mock_detect(text: str, force: bool = False, enable_news_gate: bool = False):
        return ScoreResult(
            label="needs_context",
            confidence=0.5,
            score=50,
            reasons=["样例"],
            strategy=StrategyConfig(),
        )

    monkeypatch.setattr(routes_detect, "ingest_multimodal", _mock_ingest)
    monkeypatch.setattr(routes_detect, "detect_risk_snapshot", _mock_detect)
    monkeypatch.setattr(routes_detect, "_MAX_INPUT_CHARS", 10)

    client = TestClient(app)
    response = client.post("/detect/multimodal", json={"text": "测试"})
    body = response.json()
    assert response.status_code == 200
    assert body["truncated"] is True
