import os
from pathlib import Path


_LOADED = False


def load_env(env_path=None):
    global _LOADED
    if _LOADED:
        return

    path = Path(env_path) if env_path else Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        _LOADED = True
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

    _LOADED = True


def get_env(key, default=None):
    load_env()
    return os.getenv(key, default)


def get_bool_env(key, default=False):
    value = get_env(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
