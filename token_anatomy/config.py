import os
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CLAUDE_DIR", Path.home() / ".claude"))
PORT       = int(os.environ.get("PORT", 3456))
RATES      = {
    "input":       float(os.environ.get("RATE_INPUT",       "3.0")),
    "output":      float(os.environ.get("RATE_OUTPUT",      "15.0")),
    "cache_read":  float(os.environ.get("RATE_CACHE_READ",  "0.30")),
    "cache_write": float(os.environ.get("RATE_CACHE_WRITE", "3.75")),
}
