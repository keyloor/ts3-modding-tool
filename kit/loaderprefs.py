"""Read shared game/language preferences without overwriting authoring-project settings."""
import json
import os
from pathlib import Path
import tempfile


def location():
    return Path(os.environ.get('TS3TOOL_SETTINGS') or Path.home() / '.ts3_modding_tool.json')


def read():
    try:
        data = json.loads(location().read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(**changes):
    if set(changes) - {'game', 'lang'}:
        raise ValueError('Loader preferences only include game and language.')
    path = location()
    # A broken settings file is preserved for recovery, rather than silently replaced.
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(data, dict):
        raise ValueError('Invalid settings file; preserve it for recovery.')
    data.update(changes)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
        json.dump(data, stream, ensure_ascii=False, indent=1)
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
