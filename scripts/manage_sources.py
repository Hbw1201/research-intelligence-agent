from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings
from backend.services.source_registry import SourceRecord, SourceRegistry


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the lightweight source registry.")
    parser.add_argument(
        "--registry-path",
        default=None,
        help="Path to source registry JSON. Defaults to SOURCE_REGISTRY_PATH.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List registered sources.")
    list_parser.add_argument("--source-type", default=None, help="Optional source_type filter.")
    list_parser.add_argument("--all", action="store_true", help="Include disabled sources.")

    add_parser = subparsers.add_parser("add", help="Add or update one source.")
    add_parser.add_argument("--name", required=True, help="Human-readable source name.")
    add_parser.add_argument("--url", required=True, help="Source URL.")
    add_parser.add_argument("--source-type", required=True, help="Source type, such as website/rss/dataset.")
    add_parser.add_argument("--tags", default="", help="Comma-separated tags.")
    add_parser.add_argument("--priority", type=float, default=1.0, help="Source priority.")
    add_parser.add_argument("--disabled", action="store_true", help="Add source as disabled.")

    disable_parser = subparsers.add_parser("disable", help="Disable a source by source_id or URL.")
    disable_parser.add_argument("source_id_or_url", help="Source ID, URL, or domain to disable.")

    block_parser = subparsers.add_parser("block-domain", help="Block a domain and disable matching sources.")
    block_parser.add_argument("domain", help="Domain to block.")

    subparsers.add_parser("export", help="Print the full registry JSON document.")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry = SourceRegistry(args.registry_path or get_settings().source_registry_path)

    if args.command == "list":
        records = registry.load() if args.all else registry.list_enabled(args.source_type)
        if args.all and args.source_type:
            records = [record for record in records if record.source_type == args.source_type]
        print(format_source_table(records))
        return 0

    if args.command == "add":
        record = registry.build_record(
            name=args.name,
            url=args.url,
            source_type=args.source_type,
            tags=split_csv(args.tags),
            priority=args.priority,
            enabled=not args.disabled,
            discovered_from="manual",
        )
        change = registry.add_or_update(record)
        if change.status == "blocked":
            print(f"Skipped blocked domain: {record.domain}")
            return 2
        print(f"{change.status}: {change.record.source_id if change.record else record.source_id}")
        return 0

    if args.command == "disable":
        disabled = registry.disable(args.source_id_or_url)
        print("disabled" if disabled else "not found")
        return 0 if disabled else 1

    if args.command == "block-domain":
        added = registry.block_domain(args.domain)
        print("blocked" if added else "already blocked")
        return 0

    if args.command == "export":
        print(json.dumps(registry.export_document(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


def format_source_table(records: list[SourceRecord]) -> str:
    if not records:
        return "No sources."

    lines = ["source_id\tsource_type\tenabled\tpriority\tdomain\tname\turl"]
    for record in records:
        lines.append(
            "\t".join(
                [
                    record.source_id,
                    record.source_type,
                    str(record.enabled).lower(),
                    f"{record.priority:g}",
                    record.domain,
                    record.name,
                    record.url,
                ]
            )
        )
    return "\n".join(lines)


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


if __name__ == "__main__":
    raise SystemExit(run())
