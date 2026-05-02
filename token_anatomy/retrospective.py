"""
token_anatomy/retrospective.py

Computes two analytics surfaces from session text + metadata:
  1. topic_clusters  — keyword-frequency topic grouping
  2. working_styles  — behavioral fingerprint from session metadata
"""

import re
from collections import Counter, defaultdict
from datetime import datetime

TOPIC_TAXONOMY = [
    ("Coding & Debugging",      ["bug", "error", "fix", "debug", "function", "class",
                                  "refactor", "syntax", "exception", "import", "module",
                                  "script", "code", "implement", "algorithm", "test",
                                  "pytest", "unittest", "compile", "runtime"]),
    ("Data & Analysis",         ["dataframe", "pandas", "numpy", "csv", "json", "sql",
                                  "database", "query", "dataset", "analysis", "statistics",
                                  "plot", "chart", "graph", "visualization", "correlation",
                                  "regression", "model", "train", "predict"]),
    ("Writing & Documentation", ["write", "draft", "document", "readme", "report",
                                  "essay", "summarize", "explain", "describe", "paragraph",
                                  "thesis", "paper", "abstract", "introduction", "chapter"]),
    ("Research & Literature",   ["paper", "study", "research", "literature", "survey",
                                  "citation", "reference", "review", "methodology",
                                  "hypothesis", "finding", "experiment", "result"]),
    ("DevOps & Infrastructure", ["docker", "deploy", "server", "nginx", "cloud", "aws",
                                  "github", "git", "ci", "pipeline", "bash", "shell",
                                  "linux", "ssh", "environment", "config", "setup"]),
    ("Security & Networking",   ["security", "vulnerability", "firewall", "network",
                                  "protocol", "packet", "cybersecurity", "encrypt",
                                  "authentication", "ics", "scada", "cve", "attack",
                                  "satellite", "latency", "throughput", "bandwidth"]),
    ("UI & Design",             ["ui", "ux", "frontend", "html", "css", "react",
                                  "component", "layout", "design", "style", "button",
                                  "dashboard", "interface", "responsive", "template"]),
    ("Planning & Strategy",     ["plan", "roadmap", "strategy", "goal", "task",
                                  "project", "milestone", "schedule", "priority",
                                  "brainstorm", "idea", "proposal", "feature"]),
]

STOPWORDS = {
    "the","a","an","is","it","in","of","to","and","or","for","with","this",
    "that","be","are","was","were","have","has","had","do","does","did","not",
    "on","at","by","from","as","i","we","my","you","your","can","will","how",
    "what","which","when","where","why","if","but","so","also","just","more",
    "than","then","they","their","there","use","used","using","get","set",
    "let","make","need","want","would","could","should","may","might","must",
    "like","well","good","time","way","new","all","some","any","one","two",
    "please","help","hello","hi","thank","thanks","okay","ok","yes","no",
}


def _score_session(text: str) -> dict:
    words = re.findall(r"[a-z]+", text.lower())
    word_set = Counter(w for w in words if w not in STOPWORDS and len(w) > 2)
    scores = {}
    for label, keywords in TOPIC_TAXONOMY:
        score = sum(word_set.get(kw, 0) for kw in keywords)
        if score:
            scores[label] = score
    return scores


def compute_topic_clusters(sessions: list) -> list:
    cluster_sessions = defaultdict(list)
    cluster_tokens   = defaultdict(int)

    for s in sessions:
        text   = s.get("full_text", "")
        scores = _score_session(text)
        best   = max(scores, key=scores.get) if scores else "General / Other"
        cluster_sessions[best].append(s)
        cluster_tokens[best] += s.get("input", 0) + s.get("output", 0)

    total_sessions = len(sessions) or 1
    results = []
    for label, sess_list in cluster_sessions.items():
        all_text = " ".join(s.get("full_text", "") for s in sess_list)
        words    = re.findall(r"[a-z]+", all_text.lower())
        word_freq = Counter(w for w in words if w not in STOPWORDS and len(w) > 3)
        top_kw   = [w for w, _ in word_freq.most_common(6)]
        results.append({
            "label":         label,
            "session_count": len(sess_list),
            "token_weight":  cluster_tokens[label],
            "pct":           round(len(sess_list) / total_sessions * 100, 1),
            "top_keywords":  top_kw,
        })

    matched = sum(len(v) for v in cluster_sessions.values())
    if matched < len(sessions):
        unmatched = len(sessions) - matched
        results.append({
            "label":         "General / Other",
            "session_count": unmatched,
            "token_weight":  0,
            "pct":           round(unmatched / total_sessions * 100, 1),
            "top_keywords":  [],
        })

    return sorted(results, key=lambda x: x["session_count"], reverse=True)


def _session_duration_minutes(s: dict):
    try:
        fmt = "%Y-%m-%dT%H:%M:%S"
        t0  = datetime.strptime(str(s["first_ts"])[:19], fmt)
        t1  = datetime.strptime(str(s["last_ts"])[:19],  fmt)
        return max(0.0, (t1 - t0).total_seconds() / 60)
    except Exception:
        return None


def compute_working_styles(sessions: list, hourly: list) -> list:
    if not sessions:
        return []

    styles = []
    n = len(sessions)

    # 1. Deep Diver vs Quick Querier
    avg_msgs = sum(s.get("messages", 0) for s in sessions) / n
    if avg_msgs >= 30:
        styles.append({
            "label":       "Deep Diver",
            "icon":        "🤿",
            "description": "You run long, multi-turn sessions — sustained deep work with extended context.",
            "score":       min(100, int(avg_msgs * 2)),
            "evidence":    f"Avg {avg_msgs:.0f} messages/session",
        })
    elif avg_msgs <= 8:
        styles.append({
            "label":       "Quick Querier",
            "icon":        "⚡",
            "description": "You prefer short, focused sessions — targeted queries and fast turnaround.",
            "score":       min(100, int((15 - avg_msgs) * 8)),
            "evidence":    f"Avg {avg_msgs:.0f} messages/session",
        })
    else:
        styles.append({
            "label":       "Balanced Conversationalist",
            "icon":        "⚖️",
            "description": "You mix short and long sessions naturally — adapts to the task at hand.",
            "score":       60,
            "evidence":    f"Avg {avg_msgs:.0f} messages/session",
        })

    # 2. Hands-On Builder vs Pure Conversationalist
    sessions_with_tools = [s for s in sessions if s.get("tools")]
    tool_rate = len(sessions_with_tools) / n
    if tool_rate >= 0.6:
        all_tools: Counter = Counter()
        for s in sessions:
            for t, c in (s.get("tools") or {}).items():
                all_tools[t] += c
        top_tool = f" (most used: {all_tools.most_common(1)[0][0]})" if all_tools else ""
        styles.append({
            "label":       "Hands-On Builder",
            "icon":        "🔧",
            "description": "You heavily use agentic tools — bash, file edits, code execution. You prefer doing over describing.",
            "score":       min(100, int(tool_rate * 110)),
            "evidence":    f"Tools used in {tool_rate*100:.0f}% of sessions{top_tool}",
        })
    elif tool_rate <= 0.2:
        styles.append({
            "label":       "Pure Conversationalist",
            "icon":        "💬",
            "description": "You rarely invoke tools — preferring discussion, drafting, and ideation over execution.",
            "score":       min(100, int((1 - tool_rate) * 80)),
            "evidence":    f"Tools used in only {tool_rate*100:.0f}% of sessions",
        })

    # 3. Night Owl / Early Bird / Core Hours
    if hourly and len(hourly) == 24:
        night   = sum(hourly[22:24]) + sum(hourly[0:4])
        morning = sum(hourly[5:10])
        core    = sum(hourly[9:18])
        total_h = sum(hourly) or 1
        if night / total_h >= 0.35:
            peak_h = hourly.index(max(hourly))
            styles.append({
                "label":       "Night Owl",
                "icon":        "🦉",
                "description": "Most of your Claude Code activity happens late at night — you do your best work after dark.",
                "score":       min(100, int(night / total_h * 200)),
                "evidence":    f"{night/total_h*100:.0f}% of sessions between 10pm–4am (peak: {peak_h:02d}:00)",
            })
        elif morning / total_h >= 0.35:
            styles.append({
                "label":       "Early Bird",
                "icon":        "🌅",
                "description": "You start your Claude Code sessions early — high productivity in the morning hours.",
                "score":       min(100, int(morning / total_h * 200)),
                "evidence":    f"{morning/total_h*100:.0f}% of sessions between 5am–10am",
            })
        else:
            styles.append({
                "label":       "Core Hours Worker",
                "icon":        "🕙",
                "description": "Your Claude Code usage clusters around standard working hours.",
                "score":       min(100, int(core / total_h * 130)),
                "evidence":    f"{core/total_h*100:.0f}% of sessions during 9am–6pm",
            })

    # 4. Context Architect vs Fresh Starter
    total_in = sum(s.get("input", 0) for s in sessions)
    total_cr = sum(s.get("cache_read", 0) for s in sessions)
    cache_rate = total_cr / (total_in + total_cr) if (total_in + total_cr) else 0
    if cache_rate >= 0.6:
        styles.append({
            "label":       "Context Architect",
            "icon":        "🏗️",
            "description": "You structure prompts and conversations to maximize cache reuse — efficient and deliberate.",
            "score":       min(100, int(cache_rate * 120)),
            "evidence":    f"{cache_rate*100:.0f}% cache hit rate across all sessions",
        })
    elif cache_rate <= 0.15 and n >= 5:
        styles.append({
            "label":       "Fresh Starter",
            "icon":        "🆕",
            "description": "You begin most sessions without cached context — each conversation is a clean slate.",
            "score":       min(100, int((1 - cache_rate) * 80)),
            "evidence":    f"Only {cache_rate*100:.0f}% cache hit rate",
        })

    return styles


def compute_retrospective(sessions: list, hourly: list) -> dict:
    clusters = compute_topic_clusters(sessions)
    styles   = compute_working_styles(sessions, hourly)

    # Breadth Explorer vs Domain Specialist (needs cluster data)
    active_clusters = [c for c in clusters
                       if c["label"] != "General / Other" and c["session_count"] >= 2]
    if len(active_clusters) >= 4:
        styles.append({
            "label":       "Breadth Explorer",
            "icon":        "🗺️",
            "description": "You range across many different domains — coding, writing, research, planning — within your Claude Code sessions.",
            "score":       min(100, len(active_clusters) * 18),
            "evidence":    f"Active in {len(active_clusters)} distinct topic clusters",
        })
    elif len(active_clusters) <= 2 and len(sessions) >= 5:
        top = clusters[0]["label"] if clusters else "one area"
        pct = clusters[0]["pct"] if clusters else 0
        styles.append({
            "label":       "Domain Specialist",
            "icon":        "🎯",
            "description": "Your sessions concentrate heavily in one or two areas — focused, expert-level engagement.",
            "score":       85,
            "evidence":    f"~{pct}% of sessions in '{top}'",
        })

    return {
        "topic_clusters": clusters,
        "working_styles": styles,
    }
