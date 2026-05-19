from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings
from backend.services.topic_registry import TopicRecord, TopicRegistry


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the AI + bioinformatics topic registry.")
    parser.add_argument(
        "--registry-path",
        default=None,
        help="Path to topic registry JSON. Defaults to TOPIC_REGISTRY_PATH.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List enabled topics.")
    list_parser.add_argument("--all", action="store_true", help="Include disabled topics.")
    list_parser.add_argument("--min-score", type=float, default=0.0, help="Minimum topic score.")
    list_parser.add_argument("--limit", type=int, default=None, help="Maximum topics to show.")

    add_parser = subparsers.add_parser("add", help="Add or update one topic.")
    add_parser.add_argument("--topic", required=True, help="Topic text.")
    add_parser.add_argument("--aliases", default="", help="Comma-separated aliases.")
    add_parser.add_argument("--score", type=float, default=0.5, help="Topic score between 0 and 1.")
    add_parser.add_argument("--disabled", action="store_true", help="Add topic as disabled.")

    disable_parser = subparsers.add_parser("disable", help="Disable a topic by topic text or alias.")
    disable_parser.add_argument("topic_or_alias", help="Topic or alias to disable.")

    subparsers.add_parser("export", help="Print the full topic registry JSON.")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry = TopicRegistry(args.registry_path or get_settings().topic_registry_path)

    if args.command == "list":
        if args.all:
            records = registry.load()
            records = [record for record in records if record.score >= args.min_score]
            if args.limit is not None:
                records = records[: max(0, args.limit)]
        else:
            records = registry.list_enabled(min_score=args.min_score, limit=args.limit)
        print(format_topic_table(records))
        return 0

    if args.command == "add":
        record = registry.build_record(
            topic=args.topic,
            aliases=split_csv(args.aliases),
            score=args.score,
            enabled=not args.disabled,
        )
        change = registry.add_or_update(record)
        print(f"{change.status}: {change.record.topic if change.record else record.topic}")
        return 0

    if args.command == "disable":
        disabled = registry.disable(args.topic_or_alias)
        print("disabled" if disabled else "not found")
        return 0 if disabled else 1

    if args.command == "export":
        print(json.dumps(registry.export_document(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


def format_topic_table(records: list[TopicRecord]) -> str:
    if not records:
        return "No topics."

    lines = ["topic\tlanguage\tenabled\tscore\tsource_count\titem_count\taliases"]
    for record in records:
        lines.append(
            "\t".join(
                [
                    record.topic,
                    record.language,
                    str(record.enabled).lower(),
                    f"{record.score:.3g}",
                    str(record.source_count),
                    str(record.item_count),
                    ",".join(record.aliases),
                ]
            )
        )
    return "\n".join(lines)


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


if __name__ == "__main__":
    raise SystemExit(run())
