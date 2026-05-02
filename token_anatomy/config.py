import os
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CLAUDE_DIR", Path.home() / ".claude"))
PORT       = int(os.environ.get("PORT", 3456))

# Global fallback rates (env-overridable, USD per 1M tokens)
RATES = {
    "input":       float(os.environ.get("RATE_INPUT",       "3.0")),
    "output":      float(os.environ.get("RATE_OUTPUT",      "15.0")),
    "cache_read":  float(os.environ.get("RATE_CACHE_READ",  "0.30")),
    "cache_write": float(os.environ.get("RATE_CACHE_WRITE", "3.75")),
}

# Per-model rates (Anthropic API list prices, USD per 1M tokens)
# Keys are model family strings with date suffixes stripped (split at "-20")
MODEL_RATES = {
    # Claude 4.x
    "claude-opus-4-7":   {"input": 15.0,  "output": 75.0,  "cache_read": 1.50, "cache_write": 18.75},
    "claude-opus-4-6":   {"input": 15.0,  "output": 75.0,  "cache_read": 1.50, "cache_write": 18.75},
    "claude-sonnet-4-6": {"input":  3.0,  "output": 15.0,  "cache_read": 0.30, "cache_write":  3.75},
    "claude-sonnet-4-5": {"input":  3.0,  "output": 15.0,  "cache_read": 0.30, "cache_write":  3.75},
    "claude-haiku-4-5":  {"input":  0.80, "output":  4.0,  "cache_read": 0.08, "cache_write":  1.00},
    # Claude 3.x
    "claude-opus-3":     {"input": 15.0,  "output": 75.0,  "cache_read": 1.50, "cache_write": 18.75},
    "claude-sonnet-3-7": {"input":  3.0,  "output": 15.0,  "cache_read": 0.30, "cache_write":  3.75},
    "claude-sonnet-3-5": {"input":  3.0,  "output": 15.0,  "cache_read": 0.30, "cache_write":  3.75},
    "claude-haiku-3-5":  {"input":  0.80, "output":  4.0,  "cache_read": 0.08, "cache_write":  1.00},
    "claude-haiku-3":    {"input":  0.25, "output":  1.25, "cache_read": 0.03, "cache_write":  0.30},
}


def get_rates(model_str: str) -> dict:
    family = model_str.split("-20")[0] if model_str else ""
    return MODEL_RATES.get(family, RATES)
