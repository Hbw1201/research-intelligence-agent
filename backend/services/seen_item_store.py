from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.collectors.base import ResearchItem
from backend.services.item_fingerprint import item_fingerprint


logger = logging.getLogger(__name__)


class SeenItemStore:
    """Append-only JSONL store for history-based item deduplication."""

    def __init__(self, path: str | Path = "data/seen_items.jsonl") -> None:
        self.path = Path(path)

    def load_seen(self) -> set[str]:
        """Load fingerprints that have already been recorded in the JSONL store."""
        if not self.path.exists():
            return set()

        seen: set[str] = set()
        with self.path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                record_text = line.strip()
                if not record_text:
                    continue
                try:
                    record = json.loads(record_text)
                except json.JSONDecodeError:
                    logger.warning(
                        "Skipping malformed seen-item JSONL record",
                        extra={"path": str(self.path), "line_number": line_number},
                    )
                    continue
                fingerprint = str(record.get("fingerprint") or "").strip()
                if fingerprint:
                    seen.add(fingerprint)
        return seen

    def is_seen(self, item: ResearchItem) -> bool:
        """Return whether an item fingerprint already exists in the store."""
        return item_fingerprint(item) in self.load_seen()

    def mark_seen(self, items: list[ResearchItem], pushed: bool = False) -> None:
        """Append unseen item fingerprints to the JSONL store."""
        if not items:
            return

        existing = self.load_seen()
        pushed_fingerprints = self._load_pushed()
        records: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()

        for item in items:
            fingerprint = item_fingerprint(item)
            if not fingerprint:
                continue
            if pushed:
                if fingerprint in pushed_fingerprints:
                    continue
                pushed_fingerprints.add(fingerprint)
            elif fingerprint in existing:
                continue
            existing.add(fingerprint)
            records.append(self._record(item=item, fingerprint=fingerprint, pushed=pushed, seen_at=now))

        if not records:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def filter_new_items(self, items: list[ResearchItem]) -> list[ResearchItem]:
        """Return only items whose fingerprints are not present in the store."""
        seen = self.load_seen()
        included: list[ResearchItem] = []
        included_fingerprints: set[str] = set()
        for item in items:
            fingerprint = item_fingerprint(item)
            if fingerprint in seen or fingerprint in included_fingerprints:
                continue
            included.append(item)
            included_fingerprints.add(fingerprint)
        return included

    def _load_pushed(self) -> set[str]:
        if not self.path.exists():
            return set()

        pushed: set[str] = set()
        with self.path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                record_text = line.strip()
                if not record_text:
                    continue
                try:
                    record = json.loads(record_text)
                except json.JSONDecodeError:
                    logger.warning(
                        "Skipping malformed seen-item JSONL record",
                        extra={"path": str(self.path), "line_number": line_number},
                    )
                    continue
                fingerprint = str(record.get("fingerprint") or "").strip()
                if fingerprint and record.get("pushed") is True:
                    pushed.add(fingerprint)
        return pushed

    @staticmethod
    def _record(item: ResearchItem, fingerprint: str, pushed: bool, seen_at: str) -> dict[str, Any]:
        return {
            "fingerprint": fingerprint,
            "pushed": pushed,
            "seen_at": seen_at,
            "title": item.title,
            "url": item.url,
            "source_name": item.source_name,
            "source_type": item.source_type,
            "item_type": item.item_type,
            "external_id": item.external_id,
            "published_at": item.published_at.isoformat() if item.published_at else None,
        }


def research_item_from_record(record: dict[str, Any]) -> ResearchItem | None:
    """Best-effort helper for tests and diagnostics that need to inspect JSONL records."""
    try:
        return ResearchItem.model_validate(record)
    except ValidationError:
        return None


__all__ = ["SeenItemStore", "research_item_from_record"]
