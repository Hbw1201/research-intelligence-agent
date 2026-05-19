from __future__ import annotations

import json
from pathlib import Path

from scripts import manage_sources


def test_manage_sources_cli_add_list_disable_and_block_domain(
    tmp_path: Path,
    capsys,
) -> None:
    registry_path = tmp_path / "source_registry.json"

    add_code = manage_sources.run(
        [
            "--registry-path",
            str(registry_path),
            "add",
            "--name",
            "Nature Single Cell",
            "--url",
            "https://www.nature.com/subjects/single-cell-analysis",
            "--source-type",
            "website",
            "--tags",
            "single-cell,nature",
        ]
    )
    add_output = capsys.readouterr().out

    list_code = manage_sources.run(["--registry-path", str(registry_path), "list"])
    list_output = capsys.readouterr().out

    disable_code = manage_sources.run(
        [
            "--registry-path",
            str(registry_path),
            "disable",
            "https://www.nature.com/subjects/single-cell-analysis",
        ]
    )
    disable_output = capsys.readouterr().out

    list_after_disable_code = manage_sources.run(["--registry-path", str(registry_path), "list"])
    list_after_disable_output = capsys.readouterr().out

    block_code = manage_sources.run(["--registry-path", str(registry_path), "block-domain", "reddit.com"])
    block_output = capsys.readouterr().out

    export_code = manage_sources.run(["--registry-path", str(registry_path), "export"])
    export_output = capsys.readouterr().out

    assert add_code == 0
    assert add_output.startswith("added: src_")
    assert list_code == 0
    assert "Nature Single Cell" in list_output
    assert "nature.com" in list_output
    assert disable_code == 0
    assert disable_output.strip() == "disabled"
    assert list_after_disable_code == 0
    assert list_after_disable_output.strip() == "No sources."
    assert block_code == 0
    assert block_output.strip() == "blocked"
    assert export_code == 0
    exported = json.loads(export_output)
    assert exported["blocked_domains"] == ["reddit.com"]
    assert exported["sources"][0]["enabled"] is False


def test_manage_sources_cli_add_skips_blocked_domain(tmp_path: Path, capsys) -> None:
    registry_path = tmp_path / "source_registry.json"
    manage_sources.run(["--registry-path", str(registry_path), "block-domain", "reddit.com"])
    capsys.readouterr()

    exit_code = manage_sources.run(
        [
            "--registry-path",
            str(registry_path),
            "add",
            "--name",
            "Blocked",
            "--url",
            "https://reddit.com/r/science",
            "--source-type",
            "blog",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert output.strip() == "Skipped blocked domain: reddit.com"
