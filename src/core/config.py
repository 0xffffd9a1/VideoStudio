import json
import os

DEFAULT_SETTINGS = {
    "appearance_mode": "Dark",
    "color_theme": "blue",
    "output_dir": "",
    "youtube_quality": "best",  # best, 1080p, 720p, audio_only
    "language": "ru"
}

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "settings.json")

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        settings = {}
    return {**DEFAULT_SETTINGS, **settings}

def save_settings_to_file(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)