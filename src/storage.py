import json
from pathlib import Path

from src.config import HISTORY_FILE, MAX_SEEN_LINKS


def load_seen_links(path=HISTORY_FILE):
    file_path = Path(path)
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    return []


def save_seen_links(links, path=HISTORY_FILE, max_items=MAX_SEEN_LINKS):
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    recent_links = links[-max_items:]
    tmp_path = file_path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(recent_links, f, ensure_ascii=False, indent=2)
    tmp_path.replace(file_path)
