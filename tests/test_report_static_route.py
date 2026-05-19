from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.main import create_app


def test_reports_static_route_serves_latest_html(tmp_path: Path, monkeypatch) -> None:
    report_dir = tmp_path / "reports" / "site"
    report_dir.mkdir(parents=True)
    (report_dir / "latest.html").write_text("<html>latest</html>", encoding="utf-8")
    monkeypatch.setenv("REPORT_SITE_DIR", str(report_dir))
    get_settings.cache_clear()

    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/reports/latest.html")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert "latest" in response.text
