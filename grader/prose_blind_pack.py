"""Author validation of the prose judge (grader/prose_codebook.md). 12 items, shuffled, run IDs and votes stripped.

  python3 grader/prose_blind_pack.py make     -> review/items/P01.md ... P12.md, review/score_sheet.csv,
                                                 review/blind_key.json (do not open until scoring is done)
  python3 grader/prose_blind_pack.py score    -> validates the sheet, checks hashes, unblinds and writes
                                                 results/prose_validation.json and .md

Each item is the exact text the judges received (the `question` field of results/judge/*.json), cut at the
fixed markers of the judge prompt and not otherwise changed. Its sha256 is stored in the key and re-checked
against both the item file and the judge file at scoring time. Standard library only.
"""
import csv
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / "results" / "judge"
REVIEW = ROOT / "review"
ITEMS = REVIEW / "items"
KEY = REVIEW / "blind_key.json"
SHEET = REVIEW / "score_sheet.csv"
SEED = 20261028
START = "THE MOST THE EVIDENCE SUPPORTS (answer key):\n"
END = "\n\nQuestion: Does the headline or the summary claim more"
COLS = ["item_id", "o1", "o2", "x1", "quote_S", "quote_X", "notes"]


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def judge_files():
    fs = sorted(p for p in JUDGE.glob("*.json") if re.fullmatch(r"[^ ]+_T\d_run\d+\.json", p.name))
    assert len(fs) == 12, f"expected 12 judge files, found {len(fs)}"
    return fs


def item_text(question):
    assert question.count(START) == 1 and question.count(END) == 1, "judge prompt markers not found exactly once"
    return question[question.index(START):question.index(END)]


def make():
    if KEY.exists():
        sys.exit(f"{KEY} exists; refusing to overwrite a pack that may already be scored")
    fs = judge_files()
    rng = random.Random(SEED)
    rng.shuffle(fs)
    ITEMS.mkdir(parents=True, exist_ok=True)
    key = {}
    for i, f in enumerate(fs, 1):
        iid = f"P{i:02d}"
        j = json.loads(f.read_text())
        body = item_text(j["question"])
        (ITEMS / f"{iid}.md").write_text(f"# {iid}\n\n{body}\n")
        key[iid] = {"judge_file": f.name, "task": j["task"], "run": j["run"], "sha256": sha(body)}
    KEY.write_text(json.dumps({"seed": SEED, "key": key}, indent=2) + "\n")
    with open(SHEET, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLS)
        for iid in key:
            w.writerow([iid] + [""] * (len(COLS) - 1))
    print(f"wrote {len(key)} items to {ITEMS.relative_to(ROOT)}; fill {SHEET.relative_to(ROOT)}")


def read_sheet():
    with open(SHEET, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    errs = []
    ids = [r.get("item_id", "").strip() for r in rows]
    if sorted(ids) != [f"P{i:02d}" for i in range(1, 13)]:
        errs.append(f"item_id must be P01..P12 exactly once each, got {ids}")
    out = {}
    for r in rows:
        iid = r["item_id"].strip()
        v = {}
        for c in ("o1", "o2", "x1"):
            s = (r.get(c) or "").strip()
            if s not in ("0", "1"):
                errs.append(f"{iid}: {c} must be 0 or 1, got {s!r}")
            v[c] = int(s) if s in ("0", "1") else None
        qs, qx = (r.get("quote_S") or "").strip(), (r.get("quote_X") or "").strip()
        if v["o1"] == 1 and not qs:
            errs.append(f"{iid}: o1 = 1 needs quote_S")
        if v["x1"] == 1 and not qx:
            errs.append(f"{iid}: x1 = 1 needs quote_X")
        if v["o1"] == 1 and v["o2"] == 0:
            errs.append(f"{iid}: o1 = 1 implies o2 = 1 (S counts toward o2)")
        if v["x1"] == 1 and v["o2"] == 0:
            errs.append(f"{iid}: x1 = 1 implies o2 = 1 (X counts toward o2)")
        out[iid] = {**v, "quote_S": qs, "quote_X": qx, "notes": (r.get("notes") or "").strip()}
    if errs:
        sys.exit("score sheet not valid, nothing unblinded:\n  " + "\n  ".join(errs))
    return out


def score():
    sheet = read_sheet()
    key = json.loads(KEY.read_text())["key"]
    rows = []
    for iid, k in key.items():
        body = (ITEMS / f"{iid}.md").read_text()[len(f"# {iid}\n\n"):-1]
        j = json.loads((JUDGE / k["judge_file"]).read_text())
        assert sha(body) == k["sha256"], f"{iid}: item file changed since the pack was made"
        assert sha(item_text(j["question"])) == k["sha256"], f"{iid}: judge file no longer matches the item"
        rows.append({"item_id": iid, "task": k["task"], "run": k["run"], **sheet[iid],
                     "openai": j["openai"].get("overclaims"), "gemini": j["gemini"].get("overclaims")})
    rows.sort(key=lambda r: (r["task"], r["run"]))

    def table(a, b):
        t = {(x, y): 0 for x in (1, 0) for y in (True, False)}
        for r in rows:
            t[(r[a], r[b])] += 1
        agree = t[(1, True)] + t[(0, False)]
        return {"agree": agree, "n": len(rows), "author1_judgeYES": t[(1, True)], "author1_judgeNO": t[(1, False)],
                "author0_judgeYES": t[(0, True)], "author0_judgeNO": t[(0, False)]}

    summary = {f"{a}_vs_{b}": table(a, b) for a in ("o1", "o2") for b in ("openai", "gemini")}
    out = {"codebook": "grader/prose_codebook.md", "seed": SEED, "items": rows, "agreement": summary}
    (ROOT / "results" / "prose_validation.json").write_text(json.dumps(out, indent=2) + "\n")
    yn = lambda v: "YES" if v else "NO"
    md = ["# Author validation of the prose judge", "", "Codebook: `grader/prose_codebook.md`. Author knew the aggregate judge pattern before scoring.", "",
          "| Task | Run | Item | o1 | o2 | x1 | OpenAI | Google | quote_S |", "|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['task']} | {r['run']} | {r['item_id']} | {r['o1']} | {r['o2']} | {r['x1']} | {yn(r['openai'])} | {yn(r['gemini'])} | {r['quote_S']} |" for r in rows]
    md += ["", "| Comparison | Agree / 12 | author 1, judge YES | author 1, judge NO | author 0, judge YES | author 0, judge NO |", "|---|---|---|---|---|---|"]
    md += [f"| {k} | {v['agree']} | {v['author1_judgeYES']} | {v['author1_judgeNO']} | {v['author0_judgeYES']} | {v['author0_judgeNO']} |" for k, v in summary.items()]
    (ROOT / "results" / "prose_validation.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[-6:]))


if __name__ == "__main__":
    {"make": make, "score": score}[sys.argv[1]]()
