from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    enabled = str(os.getenv("QA_FULLSTACK", "")).strip().lower() in {"1", "true", "yes"}
    if enabled:
        return

    marker = pytest.mark.skip(reason="full-stack QA requires QA_FULLSTACK=1 and the dev stand")
    qa_root = Path(__file__).resolve().parent
    for item in items:
        item_path = Path(str(item.fspath)).resolve()
        if item_path.is_relative_to(qa_root):
            item.add_marker(marker)
