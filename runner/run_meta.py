"""Summarize one run's stream-json trace: exact model string, turns, duration, cost, usage, errors.
Usage: python3 runner/run_meta.py <run_dir> <exit_code> <seconds> <model_alias>
"""
import json
import sys
from pathlib import Path

run, rc, secs, alias = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
meta = {"exit_code": rc, "wall_seconds": secs, "model_alias": alias, "model": None, "num_turns": None,
        "total_cost_usd_equiv": None, "usage": None, "result_subtype": None, "is_error": None,
        "tool_calls": 0, "answer_json_present": (run / "answer.json").exists()}
models = set()
for line in (run / "trace.jsonl").read_text(errors="replace").splitlines():
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        continue
    if ev.get("type") == "system" and ev.get("subtype") == "init":
        meta["model"] = ev.get("model")
        meta["claude_code_version"] = ev.get("claude_code_version")
        meta["api_key_source"] = ev.get("apiKeySource")
        meta["tools_available"] = ev.get("tools")
    elif ev.get("type") == "assistant":
        msg = ev.get("message", {})
        if msg.get("model"):
            models.add(msg["model"])
        meta["tool_calls"] += sum(1 for c in msg.get("content", []) if c.get("type") == "tool_use")
    elif ev.get("type") == "result":
        meta.update(num_turns=ev.get("num_turns"), total_cost_usd_equiv=ev.get("total_cost_usd"),
                    usage=ev.get("usage"), result_subtype=ev.get("subtype"), is_error=ev.get("is_error"),
                    duration_api_ms=ev.get("duration_api_ms"))
        if ev.get("is_error"):
            meta["error_text"] = str(ev.get("result"))[:500]
meta["models_seen"] = sorted(models)
print(json.dumps(meta, indent=2))
