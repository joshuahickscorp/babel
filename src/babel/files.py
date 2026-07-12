from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    with Path(path).open() as file:
        return json.load(file)


def iter_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open() as file:
        for line_no, line in enumerate(file, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
    return rows


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
