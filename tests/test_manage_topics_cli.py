from __future__ import annotations

import json
from pathlib import Path

from scripts import manage_topics


def test_manage_topics_cli_list_add_disable_and_export(tmp_path: Path, capsys) -> None:
    registry_path = tmp_path / "topic_registry.json"

    add_code = manage_topics.run(
        [
            "--registry-path",
            str(registry_path),
            "add",
            "--topic",
            "cell atlas foundation model",
            "--aliases",
            "cell atlas FM",
            "--score",
            "0.7",
        ]
    )
    add_output = capsys.readouterr().out

    list_code = manage_topics.run(["--registry-path", str(registry_path), "list", "--min-score", "0.6"])
    list_output = capsys.readouterr().out

    disable_code = manage_topics.run(["--registry-path", str(registry_path), "disable", "cell atlas FM"])
    disable_output = capsys.readouterr().out

    list_after_disable_code = manage_topics.run(["--registry-path", str(registry_path), "list", "--min-score", "0.6"])
    list_after_disable_output = capsys.readouterr().out

    export_code = manage_topics.run(["--registry-path", str(registry_path), "export"])
    export_output = capsys.readouterr().out

    assert add_code == 0
    assert add_output.strip() == "added: cell atlas foundation model"
    assert list_code == 0
    assert "cell atlas foundation model" in list_output
    assert "cell atlas FM" in list_output
    assert disable_code == 0
    assert disable_output.strip() == "disabled"
    assert list_after_disable_code == 0
    assert "cell atlas foundation model" not in list_after_disable_output
    assert export_code == 0
    exported = json.loads(export_output)
    assert any(record["topic"] == "cell atlas foundation model" for record in exported["topics"])


def test_manage_topics_cli_list_includes_seed_topics(tmp_path: Path, capsys) -> None:
    exit_code = manage_topics.run(["--registry-path", str(tmp_path / "topic_registry.json"), "list", "--limit", "3"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "topic\tlanguage" in output
