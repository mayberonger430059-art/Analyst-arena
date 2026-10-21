#!/usr/bin/env python3
"""Analyst Arena - a multi-agent prediction league where ground truth is the referee.

Several AI analysts independently submit predictions (with mandatory reasoning)
before each event. Outcomes settle the score. Only disagreements are reviewed,
and lessons enter the shared knowledge base only after enough evidence
accumulates. Single file, standard library only.

Config (arena.json) declares agents, dimensions, confidence scale and the
evidence threshold, so the same engine runs a football-prediction league, a
stock-call league, an election-forecast league, or your own contest.
"""
import argparse, json, sqlite3, sys, os
from datetime import datetime

DEFAULT_CONFIG = {
    "agents": {"alpha": "Alpha", "bravo": "Bravo", "charlie": "Charlie"},
    "confidences": ["high", "medium", "low"],
    "push_min_confidence": "medium",
    "dimensions": {"call": {"kind": "hitmiss"}},
    "nobet_codes": ["LOW_CONFIDENCE", "INSUFFICIENT_INFO",
                    "CONFLICTING_SIGNALS", "NO_EDGE", "OTHER"],
    "learning_min_samples": 10,
    "db": "data/arena.db",
}
GRADED = ("win", "half_win", "push", "half_lose", "lose", "na")
GRADED_POINTS = {"win": 1.0, "half_win": 0.5, "push": None,
                 "half_lose": 0.5, "lose": 0.0, "na": None}

CFG = dict(DEFAULT_CONFIG)
BASE_DIR = os.getcwd()


def load_config(path):
    global CFG, BASE_DIR
    if path:
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        CFG = {**DEFAULT_CONFIG, **user}
        BASE_DIR = os.path.dirname(os.path.abspath(path))
    return CFG


def db_path():
    p = CFG["db"]
    return p if os.path.isabs(p) else os.path.join(BASE_DIR, p)


def db():
    os.makedirs(os.path.dirname(db_path()), exist_ok=True)
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS submissions(
      id INTEGER PRIMARY KEY,
      date TEXT NOT NULL, agent TEXT NOT NULL,
      match_id TEXT NOT NULL, title TEXT, kickoff TEXT,
      dim TEXT NOT NULL, pick TEXT, conf TEXT,
      nobet_code TEXT, orig_pick TEXT, orig_conf TEXT,
      reasons TEXT NOT NULL, pushed INTEGER NOT NULL,
      submitted_at TEXT NOT NULL,
      UNIQUE(date, agent, match_id, dim));
    CREATE TABLE IF NOT EXISTS results(
      date TEXT NOT NULL, match_id TEXT NOT NULL,
      dim TEXT NOT NULL, agent TEXT NOT NULL, outcome TEXT,
      PRIMARY KEY(date, match_id, dim, agent));
    CREATE TABLE IF NOT EXISTS learnings(
      id INTEGER PRIMARY KEY, date_added TEXT NOT NULL,
      title TEXT NOT NULL, evidence TEXT, n INTEGER DEFAULT 1,
      level TEXT DEFAULT 'L1', status TEXT DEFAULT 'observing');
    """)
    c.commit(); c.close()
    print("Arena database ready:", db_path())


def conf_rank(conf):
    try:
        return CFG["confidences"].index(conf)
    except ValueError:
        return None


def is_pushed(entry):
    if not entry.get("pick"):
        return 0
    r = conf_rank(entry.get("conf"))
    return 1 if (r is not None and r <= conf_rank(CFG["push_min_confidence"])) else 0


def validate_sub(d):
    errs = []
    if not isinstance(d, dict):
        return ["top level must be an object"]
    for k in ("date", "agent", "matches"):
        if k not in d:
            errs.append("missing field: %s" % k)
    if errs:
        return errs
    try:
        datetime.strptime(d["date"], "%Y-%m-%d")
    except Exception:
        errs.append("date must be YYYY-MM-DD")
    if d["agent"] not in CFG["agents"]:
        errs.append("agent must be one of %s" % list(CFG["agents"]))
    ms = d["matches"]
    if not isinstance(ms, list) or not ms:
        errs.append("matches must be a non-empty array")
        return errs
    dims = CFG["dimensions"]
    for i, m in enumerate(ms):
        p = "matches[%d]" % i
        if "match_id" not in m:
            errs.append("%s missing match_id" % p)
        md = m.get("dims")
        if not isinstance(md, dict):
            errs.append("%s.dims must be an object" % p)
            continue
        for dim in dims:
            if dim not in md:
                errs.append("%s.dims missing dimension %s" % (p, dim))
                continue
            e = md[dim]
            q = "%s.dims.%s" % (p, dim)
            if not isinstance(e, dict):
                errs.append("%s must be an object" % q)
                continue
            rs = e.get("reasons")
            if not isinstance(rs, list) or not rs or not all(
                    isinstance(x, str) and x.strip() for x in rs):
                errs.append("%s.reasons is required: a non-empty list of "
                            "strings (the signals behind the call; "
                            "post-round attribution depends on it)" % q)
            if e.get("pick"):
                if conf_rank(e.get("conf")) is None:
                    errs.append("%s.conf must be one of %s"
                                % (q, CFG["confidences"]))
            else:
                if e.get("nobet_code") not in CFG["nobet_codes"]:
                    errs.append("%s: no pick requires nobet_code in %s"
                                % (q, CFG["nobet_codes"]))
    return errs


def cmd_submit(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    errs = validate_sub(d)
    if errs:
        print("Submission rejected:")
        for e in errs:
            print(" -", e)
        sys.exit(1)
    c = db(); now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    n = 0
    for m in d["matches"]:
        for dim, e in m["dims"].items():
            c.execute("""INSERT OR REPLACE INTO submissions
              (date,agent,match_id,title,kickoff,dim,pick,conf,
               nobet_code,orig_pick,orig_conf,reasons,pushed,submitted_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (d["date"], d["agent"], m["match_id"], m.get("title"),
               m.get("kickoff"), dim, e.get("pick"), e.get("conf"),
               e.get("nobet_code"), e.get("orig_pick"), e.get("orig_conf"),
               json.dumps(e["reasons"], ensure_ascii=False),
               is_pushed(e), now))
            n += 1
    c.commit(); c.close()
    print("Submission locked: agent=%s date=%s, %d events / %d calls"
          % (d["agent"], d["date"], len(d["matches"]), n))


def cmd_settle(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    date = d["date"]
    c = db(); n = 0
    for m in d["matches"]:
        # Outcomes are settled per agent: two analysts on opposite sides of
        # the same line cannot share one outcome.
        for agent, outcomes in m.get("agents", {}).items():
            for dim, outcome in outcomes.items():
                kind = CFG["dimensions"].get(dim, {}).get("kind", "hitmiss")
                if kind == "graded":
                    if outcome not in GRADED:
                        print("warning: %s %s %s outcome %r invalid, "
                              "stored as 'na'"
                              % (m["match_id"], agent, dim, outcome))
                        outcome = "na"
                    val = outcome
                else:
                    val = "hit" if outcome else "miss"
                c.execute("INSERT OR REPLACE INTO results VALUES(?,?,?,?,?)",
                          (date, m["match_id"], dim, agent, val))
                n += 1
    c.commit(); c.close()
    print("Settled: %s, %d outcomes" % (date, n))


def cmd_board(date=None):
    c = db()
    dates = [r[0] for r in c.execute(
        "SELECT DISTINCT date FROM submissions ORDER BY date")]
    if date:
        dates = [date] if date in dates else []
    if not dates:
        print("Scoreboard is empty"); c.close(); return
    for dt in dates:
        print("\n===== %s scoreboard =====" % dt)
        for ag, name in CFG["agents"].items():
            rows = c.execute("""SELECT s.dim, s.pick, s.pushed, r.outcome
                FROM submissions s LEFT JOIN results r
                ON s.date=r.date AND s.match_id=r.match_id AND s.dim=r.dim
                AND s.agent=r.agent
                WHERE s.date=? AND s.agent=?""", (dt, ag)).fetchall()
            if not rows:
                print("[%s] no submission" % name); continue
            parts = []
            for dim, spec in CFG["dimensions"].items():
                dr = [r for r in rows if r["dim"] == dim]
                called = [r for r in dr if r["pick"] and r["outcome"] is not None]
                pushed = [r for r in called if r["pushed"]]
                if spec.get("kind") == "graded":
                    sc = [(r, GRADED_POINTS[r["outcome"]]) for r in pushed]
                    sc = [(r, s) for r, s in sc if s is not None]
                    tot = sum(s for _, s in sc)
                    seg = "%s pushed %.1f/%d" % (dim, tot, len(sc))
                    if sc:
                        seg += " (%.1f%%)" % (tot / len(sc) * 100)
                    parts.append(seg)
                else:
                    hp = sum(1 for r in pushed if r["outcome"] == "hit")
                    ha = sum(1 for r in called if r["outcome"] == "hit")
                    seg = "%s pushed %d/%d" % (dim, hp, len(pushed))
                    if pushed:
                        seg += " (%.1f%%)" % (hp / len(pushed) * 100)
                    seg += ", all %d/%d" % (ha, len(called))
                    parts.append(seg)
            nb = sum(1 for r in rows if not r["pick"])
            pend = sum(1 for r in rows if r["pick"] and r["outcome"] is None)
            tail = " | no-bet %d" % nb
            if pend:
                tail += " | unsettled %d" % pend
            print("[%s] %s%s" % (name, " | ".join(parts), tail))
    c.close()


def cmd_diverge(date):
    c = db()
    agents = [r[0] for r in c.execute(
        "SELECT DISTINCT agent FROM submissions WHERE date=?", (date,))]
    if len(agents) < 2:
        print("%s: only %d agent(s) submitted; divergence needs >= 2"
              % (date, len(agents))); c.close(); return
    rows = c.execute("""SELECT match_id, agent, dim, pick FROM submissions
        WHERE date=? AND pushed=1""", (date,)).fetchall()
    by_key = {}
    for r in rows:
        by_key.setdefault((r["match_id"], r["dim"]), {})[r["agent"]] = r["pick"]
    found = False
    for (mid, dim), picks in sorted(by_key.items()):
        if len(set(picks.values())) > 1:
            found = True
            print("DIVERGENCE %s [%s]: %s" % (mid, dim, " vs ".join(
                "%s=%s" % (CFG["agents"].get(a, a), p)
                for a, p in picks.items())))
    if not found:
        print("%s: no pushed divergences" % date)
    c.close()


def cmd_learn_add(title, evidence, n=1, level="L1"):
    gate = CFG["learning_min_samples"]
    if n < gate and level != "L1":
        print("Evidence gate: n=%d < %d, stored as L1 (observation only). "
              "Lessons graduate only after enough samples accumulate."
              % (n, gate))
        level = "L1"
    c = db()
    c.execute("""INSERT INTO learnings(date_added,title,evidence,n,level)
                 VALUES(?,?,?,?,?)""",
              (datetime.now().strftime("%Y-%m-%d"), title, evidence, n, level))
    c.commit(); c.close()
    print("Learning recorded:", title)


def cmd_learn_list():
    c = db()
    rows = c.execute("SELECT * FROM learnings ORDER BY id").fetchall()
    if not rows:
        print("Shared knowledge base is empty"); c.close(); return
    for r in rows:
        print("#%d [%s|%s|n=%d] %s\n    evidence: %s"
              % (r["id"], r["level"], r["status"], r["n"],
                 r["title"], r["evidence"]))
    c.close()


def main():
    ap = argparse.ArgumentParser(
        description="Analyst Arena: multi-agent prediction league")
    ap.add_argument("--config", help="path to arena.json (optional)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create the database")
    p = sub.add_parser("submit", help="validate and lock a submission")
    p.add_argument("json")
    p = sub.add_parser("settle", help="settle a round with outcomes")
    p.add_argument("json")
    p = sub.add_parser("board", help="print the scoreboard")
    p.add_argument("--date")
    p = sub.add_parser("diverge", help="list pushed divergences for a date")
    p.add_argument("date")
    p = sub.add_parser("learn-add", help="add a shared learning")
    p.add_argument("title"); p.add_argument("evidence")
    p.add_argument("--n", type=int, default=1)
    p.add_argument("--level", default="L1")
    sub.add_parser("learn-list", help="list shared learnings")
    a = ap.parse_args()
    load_config(a.config)
    if a.cmd == "init": init_db()
    elif a.cmd == "submit": cmd_submit(a.json)
    elif a.cmd == "settle": cmd_settle(a.json)
    elif a.cmd == "board": cmd_board(a.date)
    elif a.cmd == "diverge": cmd_diverge(a.date)
    elif a.cmd == "learn-add": cmd_learn_add(a.title, a.evidence, a.n, a.level)
    elif a.cmd == "learn-list": cmd_learn_list()


if __name__ == "__main__":
    main()
