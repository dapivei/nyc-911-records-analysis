"""Small helpers for saving results as we go, so every step can resume."""
import json
from pathlib import Path

import pandas as pd


def append_rows(path: Path, rows):
    """Append dicts to a .jsonl file (one JSON object per line)."""
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")


def read_rows(path: Path, columns=None) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns or [])
    df = pd.read_json(path, lines=True, dtype=False)
    return df[columns] if columns else df


def mark_done(path: Path, keys):
    with open(path, "a") as f:
        f.writelines(f"{k}\n" for k in keys)


def done_keys(path: Path) -> set:
    return set(path.read_text().split()) if path.exists() else set()


def read_table(path: Path, columns=None) -> pd.DataFrame:
    """Read .parquet or .jsonl; empty DataFrame if the file doesn't exist yet."""
    if path.suffix == ".jsonl":
        return read_rows(path, columns)
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    return pd.read_parquet(path, columns=columns)
