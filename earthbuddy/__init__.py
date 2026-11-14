"""Earth Buddy. Importing the package loads `.env`; the real environment wins."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources.json"


def _load_env(path: Path = ROOT / ".env") -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        key = key.strip()
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))   # real environment wins


_load_env()
