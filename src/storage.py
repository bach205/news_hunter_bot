import json
import os

from src.config import HISTORY_FILE, MAX_SEEN_LINKS


def load_seen_links(path=HISTORY_FILE):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    return []


def save_seen_links(links, path=HISTORY_FILE, max_items=MAX_SEEN_LINKS):
    recent_links = links[-max_items:]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(recent_links, f, ensure_ascii=False, indent=2)
