from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.wecom import PushMessage, WeComPushService


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push a saved report to a WeCom group robot webhook.")
    parser.add_argument("--report-path", required=True, help="Markdown or text report file to push.")
    parser.add_argument(
        "--message-type",
        choices=["markdown", "text"],
        default="markdown",
        help="WeCom message type to send.",
    )
    parser.add_argument("--title", default="今日科研情报", help="Message title used for logs and status output.")
    return parser.parse_args(argv)


async def push_report(
    report_path: str | Path,
    message_type: str,
    title: str,
    service: WeComPushService | None = None,
) -> None:
    path = Path(report_path)
    content = path.read_text(encoding="utf-8")
    push_service = service or WeComPushService()
    message = PushMessage(title=title, markdown=content)

    if message_type == "markdown":
        await push_service.send_markdown(message)
        return
    if message_type == "text":
        await push_service.send_text(message)
        return
    raise ValueError(f"Unsupported WeCom message type: {message_type}")


async def run(argv: list[str] | None = None, service: WeComPushService | None = None) -> int:
    args = parse_args(argv)
    try:
        await push_report(
            report_path=args.report_path,
            message_type=args.message_type,
            title=args.title,
            service=service,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should turn failures into clear stderr output.
        print(f"WeCom push failed: {exc}", file=sys.stderr)
        return 1

    print(f"Pushed WeCom {args.message_type} message: {Path(args.report_path).name}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
