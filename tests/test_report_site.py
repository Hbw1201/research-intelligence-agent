from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.services.report_site import ReportSiteWriter


def test_report_site_writes_timestamped_file_and_latest_html(tmp_path: Path) -> None:
    writer = ReportSiteWriter(
        site_dir=tmp_path / "site",
        public_base_url="https://reports.example.com/reports",
    )

    result = writer.save("<html>daily</html>", generated_at=datetime(2026, 5, 19, 8, 30, tzinfo=timezone.utc))

    assert result.report_path.name == "daily_20260519_0830.html"
    assert result.report_path.read_text(encoding="utf-8") == "<html>daily</html>"
    assert result.latest_path.name == "latest.html"
    assert result.latest_path.read_text(encoding="utf-8") == "<html>daily</html>"
    assert result.public_url == "https://reports.example.com/reports/daily_20260519_0830.html"
    assert result.latest_public_url == "https://reports.example.com/reports/latest.html"


def test_report_site_without_public_base_url_returns_local_paths_only(tmp_path: Path) -> None:
    writer = ReportSiteWriter(site_dir=tmp_path / "site", public_base_url="")

    result = writer.save("<html>daily</html>", generated_at=datetime(2026, 5, 19, 8, 30, tzinfo=timezone.utc))

    assert result.report_path.exists()
    assert result.latest_path.exists()
    assert result.public_url is None
    assert result.latest_public_url is None
