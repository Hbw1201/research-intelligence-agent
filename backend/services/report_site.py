from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ReportSiteResult:
    """Location details for a generated static HTML report."""

    report_path: Path
    latest_path: Path
    public_url: str | None
    latest_public_url: str | None


class ReportSiteWriter:
    """Write static HTML reports into a small local report site directory."""

    def __init__(
        self,
        site_dir: str | Path = "reports/site",
        public_base_url: str | None = None,
    ) -> None:
        self.site_dir = Path(site_dir)
        self.public_base_url = clean_public_base_url(public_base_url)

    def save(self, html_report: str, generated_at: datetime | None = None) -> ReportSiteResult:
        """Save a timestamped report and update latest.html."""
        timestamp = (generated_at or datetime.now(timezone.utc)).strftime("%Y%m%d_%H%M")
        self.site_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.site_dir / f"daily_{timestamp}.html"
        latest_path = self.site_dir / "latest.html"
        report_path.write_text(html_report, encoding="utf-8")
        shutil.copyfile(report_path, latest_path)
        return ReportSiteResult(
            report_path=report_path,
            latest_path=latest_path,
            public_url=self.public_url_for(report_path),
            latest_public_url=self.public_url_for(latest_path),
        )

    def public_url_for(self, path: Path) -> str | None:
        """Return a public URL for a saved report if REPORT_PUBLIC_BASE_URL is configured."""
        if not self.public_base_url:
            return None
        try:
            relative_path = path.relative_to(self.site_dir)
        except ValueError:
            relative_path = Path(path.name)
        return f"{self.public_base_url}/{relative_path.as_posix()}"


def clean_public_base_url(value: str | None) -> str | None:
    normalized = str(value or "").strip().rstrip("/")
    return normalized or None


__all__ = ["ReportSiteResult", "ReportSiteWriter", "clean_public_base_url"]
