import json
from pathlib import Path

from src.config import COOLDOWN_FILE, HISTORY_FILE, MAX_SEEN_LINKS


def _atomic_write_json(data, file_path):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(file_path)


def load_seen_links(path=HISTORY_FILE):
    file_path = Path(path)
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    return []


def save_seen_links(links, path=HISTORY_FILE, max_items=MAX_SEEN_LINKS):
    recent_links = links[-max_items:]
    _atomic_write_json(recent_links, path)


def load_cooldowns(path=COOLDOWN_FILE):
    file_path = Path(path)
    if file_path.exists():
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (ValueError, OSError):
            return {}
    return {}


def save_cooldowns(cooldowns, path=COOLDOWN_FILE):
    _atomic_write_json(cooldowns, path)
