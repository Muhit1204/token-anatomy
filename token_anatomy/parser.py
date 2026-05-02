import json
import sys
from pathlib import Path
from datetime import date, datetime
from collections import defaultdict

from token_anatomy.config import CLAUDE_DIR, RATES


def compute_cost(it=0, ot=0, cr=0, cw=0):
    return (
        it * RATES["input"]       / 1_000_000 +
        ot * RATES["output"]      / 1_000_000 +
        cr * RATES["cache_read"]  / 1_000_000 +
        cw * RATES["cache_write"] / 1_000_000
    )

def parse_data():
    projects_dir = CLAUDE_DIR / "projects"
    if not projects_dir.exists():
        return {"error": f"Claude projects directory not found: {projects_dir}"}

    # Aggregation containers
    total = defaultdict(int)        # input, output, cache_read, cache_write, msgs, sessions
    daily = defaultdict(lambda: defaultdict(int))   # day -> metric -> int
    tools = defaultdict(int)        # tool_name -> total call count
    models = defaultdict(int)       # model -> session count
    projects_stats = defaultdict(lambda: defaultdict(int))  # project -> metric
    sessions = []                   # list of per-session dicts
    hourly = defaultdict(int)       # hour (0-23) -> session count (productivity heatmap)

    project_dirs = sorted([d for d in projects_dir.iterdir() if d.is_dir()])

    for project_dir in project_dirs:
        project_key = project_dir.name
        # Try to decode the URL-encoded project path for a readable label
        try:
            from urllib.parse import unquote
            label = unquote(project_key).replace("/", " / ").strip(" / ")
            # Take just the last meaningful path segment
            parts = [p for p in label.split(" / ") if p]
            project_label = parts[-1] if parts else project_key[:24]
        except Exception:
            project_label = project_key[:24]

        jsonl_files = list(project_dir.glob("*.jsonl"))

        for jsonl_file in jsonl_files:
            sess = {
                "id":           jsonl_file.stem[:12],
                "project":      project_label,
                "project_full": project_key,
                "messages":     0,
                "input":        0,
                "output":       0,
                "cache_read":   0,
                "cache_write":  0,
                "tools":        defaultdict(int),
                "first_ts":     None,
                "last_ts":      None,
                "model":        None,
                "cost":         0.0,
            }

            try:
                with open(jsonl_file, "r", encoding="utf-8", errors="replace") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        sess["messages"] += 1
                        entry_type = entry.get("type", "")

                        # ── Timestamp ──
                        ts_raw = entry.get("timestamp") or entry.get("ts", "")
                        if ts_raw:
                            ts_str = str(ts_raw)
                            if sess["first_ts"] is None:
                                sess["first_ts"] = ts_str
                            sess["last_ts"] = ts_str

                        # ── Model ──
                        msg = entry.get("message") or {}
                        model_str = msg.get("model") or entry.get("model", "")
                        if model_str and not sess["model"]:
                            sess["model"] = model_str

                        # ── Usage (only on assistant turns) ──
                        if entry_type == "assistant":
                            usage = msg.get("usage") or entry.get("usage") or {}
                            it = int(usage.get("input_tokens", 0) or 0)
                            ot = int(usage.get("output_tokens", 0) or 0)
                            cr = int(usage.get("cache_read_input_tokens", 0) or 0)
                            cw = int(usage.get("cache_creation_input_tokens", 0) or 0)
                            sess["input"]       += it
                            sess["output"]      += ot
                            sess["cache_read"]  += cr
                            sess["cache_write"] += cw

                            # Daily aggregation
                            if ts_raw:
                                day = str(ts_raw)[:10]
                                daily[day]["input"]       += it
                                daily[day]["output"]      += ot
                                daily[day]["cache_read"]  += cr
                                daily[day]["cache_write"] += cw
                                daily[day]["messages"]    += 1

                            # Tool call extraction
                            content = msg.get("content") or entry.get("content") or []
                            if isinstance(content, list):
                                for block in content:
                                    if (isinstance(block, dict)
                                            and block.get("type") == "tool_use"):
                                        name = block.get("name", "unknown")
                                        sess["tools"][name] += 1
                                        tools[name]         += 1

            except Exception as exc:
                print(f"  [warn] Could not read {jsonl_file.name}: {exc}", file=sys.stderr)
                continue

            # ── Session-level derived values ──
            sess["cost"] = compute_cost(
                sess["input"], sess["output"],
                sess["cache_read"], sess["cache_write"]
            )
            sess["tools"] = dict(sess["tools"])

            # ── Hourly heatmap ──
            if sess["first_ts"]:
                try:
                    hour = int(sess["first_ts"][11:13])
                    hourly[hour] += 1
                except Exception:
                    pass

            # ── Per-project accumulation ──
            ps = projects_stats[project_label]
            ps["input"]       += sess["input"]
            ps["output"]      += sess["output"]
            ps["cache_read"]  += sess["cache_read"]
            ps["cache_write"] += sess["cache_write"]
            ps["sessions"]    += 1
            ps["messages"]    += sess["messages"]

            # ── Model accumulation ──
            if sess["model"]:
                short = sess["model"].split("-20")[0]   # strip date suffix
                models[short] += 1

            # ── Global totals ──
            total["input"]       += sess["input"]
            total["output"]      += sess["output"]
            total["cache_read"]  += sess["cache_read"]
            total["cache_write"] += sess["cache_write"]
            total["messages"]    += sess["messages"]
            total["sessions"]    += 1

            sessions.append(sess)

    # ── Compute daily costs & session counts ──
    for day_key, ds in daily.items():
        ds["cost"] = compute_cost(ds["input"], ds["output"],
                                  ds["cache_read"], ds["cache_write"])
        ds["sessions"] = sum(
            1 for s in sessions
            if s["first_ts"] and str(s["first_ts"])[:10] == day_key
        )

    # ── Per-project costs ──
    for pl, ps in projects_stats.items():
        ps["cost"] = compute_cost(ps["input"], ps["output"],
                                  ps["cache_read"], ps["cache_write"])

    # ── Today's stats ──
    today_key = date.today().isoformat()
    today_d   = dict(daily.get(today_key, {}))
    if not today_d:
        today_d = {"input": 0, "output": 0, "cache_read": 0,
                   "cache_write": 0, "messages": 0, "sessions": 0, "cost": 0.0}

    # ── Cache hit rate ──
    denominator = total["input"] + total["cache_read"]
    cache_hit_rate = round(total["cache_read"] / denominator * 100, 1) if denominator else 0.0

    # ── Cache savings ──
    # What input cost would have been WITHOUT cache reads (charged at full input rate)
    no_cache_cost = compute_cost(
        total["input"] + total["cache_read"], total["output"], 0, 0
    )
    actual_cost   = compute_cost(total["input"], total["output"],
                                 total["cache_read"], total["cache_write"])
    cache_savings = max(0.0, no_cache_cost - actual_cost)

    # ── Sort: daily descending, sessions by cost desc ──
    daily_sorted = dict(sorted(daily.items(), key=lambda x: x[0], reverse=True))
    sessions_sorted = sorted(sessions, key=lambda s: s["cost"], reverse=True)

    # Top tools (top 10)
    top_tools = sorted(tools.items(), key=lambda x: x[1], reverse=True)[:10]

    # Top projects (top 8 by cost)
    top_projects = sorted(
        [(k, dict(v)) for k, v in projects_stats.items()],
        key=lambda x: x[1].get("cost", 0), reverse=True
    )[:8]

    # Hourly list (0-23)
    hourly_list = [hourly.get(h, 0) for h in range(24)]

    return {
        "total":         dict(total),
        "today":         today_d,
        "daily":         {k: dict(v) for k, v in daily_sorted.items()},
        "tools":         top_tools,
        "models":        dict(models),
        "projects":      top_projects,
        "sessions":      sessions_sorted,          # all sessions
        "hourly":        hourly_list,
        "cache_hit_rate": cache_hit_rate,
        "cache_savings":  round(cache_savings, 4),
        "total_cost":     round(compute_cost(
                              total["input"], total["output"],
                              total["cache_read"], total["cache_write"]), 4),
        "rates":          RATES,
        "claude_dir":     str(CLAUDE_DIR),
        "generated_at":   datetime.now().isoformat(timespec="seconds"),
    }
