"""Find the code changes that moved anyone's rating.

Walks the git history, and for every commit that touched a .py file replays the
whole tournament corpus twice — once with the commit's tree, once with its
parent's — then reports the commits where some player's rating came out
different. That is the only way to answer the question: ratings have no
persisted state, so the effect of a code change is whatever the replay produces.

Each tree is evaluated as it was committed, i.e. that commit's code against that
commit's own data/ and results/. A commit that touched both code and data is
therefore a mixed result, and is flagged as such in the report ("data" in the
touched column). Pass --pin-data REF to overlay a single fixed data/ + results/
snapshot on every tree instead, which isolates the code — but only works for the
eras whose readers understand that snapshot (the early code hard-codes its own
tournament list and ignores data/tournaments.csv entirely).

Trees are extracted with `git archive`, so the working tree is never touched and
the script is safe to run against a dirty checkout.

    uv run python scripts/rating_history.py                    # whole history
    uv run python scripts/rating_history.py --since 2026-07-01 # recent only
    uv run python scripts/rating_history.py --pin-data HEAD    # isolate code
    uv run python scripts/rating_history.py -o report.md       # write a report

Exit status is 0 even when replays fail; failures are counted and listed, since
the oldest commits legitimately have no history-replay entry point at all.
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Entry points, newest layout first. Each is tried in turn; the first module that
# imports and exposes process_old_results wins.
#   coco_ratings.pipeline  src-layout package        (2026-07 onwards)
#   pipeline               flat module after the split
#   all_rating             the original replay driver (2022-03 onwards)
CANDIDATES = ("coco_ratings.pipeline", "pipeline", "all_rating", "rating")

# Runs inside the extracted tree, in a subprocess, so that historical module-level
# code (tkinter imports, globals, prints) cannot contaminate this process.
DRIVER = '''
import json, os, sys, io, contextlib, traceback

root, out_path = sys.argv[1], sys.argv[2]
os.chdir(root)
sys.path.insert(0, os.path.join(root, "src"))
sys.path.insert(0, root)

CANDIDATES = %(candidates)r

def extract(db):
    # process_old_results returned a bare db before it returned (db, latest).
    if isinstance(db, tuple):
        db = db[0]
    players = {}
    for name, rec in db.players.items():
        players[name] = [
            getattr(rec, "rating", None),
            getattr(rec, "deviation", None),
            getattr(rec, "games", None),
        ]
    return players

result = {"ok": False}
buf = io.StringIO()
try:
    fn = None
    tried = []
    for mod in CANDIDATES:
        try:
            m = __import__(mod, fromlist=["process_old_results"])
        except Exception as e:
            tried.append(f"{mod}: {type(e).__name__}: {e}")
            continue
        # An installed copy of the package (e.g. an editable .pth pointing at
        # the live working tree) would answer this import with TODAY's code and
        # data, silently making every old commit look identical to HEAD. Only
        # accept a module that physically lives in the extracted tree.
        origin = os.path.realpath(getattr(m, "__file__", "") or "")
        if not origin.startswith(os.path.realpath(root) + os.sep):
            tried.append(f"{mod}: resolved outside the tree ({origin})")
            sys.modules.pop(mod, None)
            continue
        fn = getattr(m, "process_old_results", None)
        if fn is not None:
            result["entry"] = mod
            result["module_file"] = origin
            break
        tried.append(f"{mod}: no process_old_results")
    if fn is None:
        result["error"] = "no entry point (" + "; ".join(tried) + ")"
    else:
        # Historical code prints progress freely; keep it out of our output.
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            db = fn()
        result["players"] = extract(db)
        result["ok"] = True
except Exception as e:
    result["error"] = f"{type(e).__name__}: {e}"
    result["traceback"] = traceback.format_exc()[-2000:]

with open(out_path, "w") as f:
    json.dump(result, f)
''' % {"candidates": CANDIDATES}


def git_bytes(*args, cwd=REPO) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, check=True
    ).stdout


def git(*args, cwd=REPO) -> str:
    return git_bytes(*args, cwd=cwd).decode()


def touched(sha):
    """Files changed by a commit (against its first parent)."""
    out = git("diff-tree", "--no-commit-id", "--name-only", "-r", "-m",
              "--first-parent", sha)
    return [ln for ln in out.splitlines() if ln]


# Until c5aa5ff05a (2025-11-16) the chronological tournament list lived in
# all_rating.py as a list of ("prefix", "yyyy-mm-dd") tuples, so adding a
# tournament *was* a .py change. Those commits move ratings, but they are data
# edits in code's clothing — worth separating from real engine changes.
TOURNAMENT_TUPLE = re.compile(r'^\s*\(\s*"[\w.-]+"\s*,\s*"[\d-]+"\s*\)\s*,?\s*$')
TRIVIAL = re.compile(r"^\s*(#.*)?$")


def classify(sha):
    """'tournament-list', 'code', or 'mixed' — what kind of .py edit this is."""
    diff = git("show", "--format=", "--unified=0", sha, "--", "*.py")
    listish = codeish = 0
    for line in diff.splitlines():
        if line[:3] in ("+++", "---") or line[:1] not in "+-":
            continue
        body = line[1:]
        if TOURNAMENT_TUPLE.match(body):
            listish += 1
        elif TRIVIAL.match(body):
            continue
        else:
            codeish += 1
    if codeish and listish:
        return "mixed"
    if codeish:
        return "code"
    if listish:
        return "tournament-list"
    return "code"


def commit_meta(sha) -> dict:
    out = git("show", "-s", "--format=%H%x00%an%x00%ad%x00%s", "--date=short", sha)
    h, author, date, subject = out.strip("\n").split("\0")
    return {"sha": h, "author": author, "date": date, "subject": subject}


def extract_tree(sha, dest, pin_data=None):
    """Materialise a commit's tree at `dest` (never touches the working tree)."""
    dest.mkdir(parents=True, exist_ok=True)
    blob = git_bytes("archive", "--format=tar", sha)
    with tempfile.NamedTemporaryFile(suffix=".tar") as tf:
        tf.write(blob)
        tf.flush()
        with tarfile.open(tf.name) as tar:
            tar.extractall(dest, filter="data")
    if pin_data:
        for sub in ("data", "results"):
            target = dest / sub
            if target.exists():
                shutil.rmtree(target)
            try:
                sub_blob = git_bytes("archive", "--format=tar", f"{pin_data}:{sub}")
            except subprocess.CalledProcessError:
                continue
            target.mkdir(parents=True)
            with tempfile.NamedTemporaryFile(suffix=".tar") as tf:
                tf.write(sub_blob)
                tf.flush()
                with tarfile.open(tf.name) as tar:
                    tar.extractall(target, filter="data")


def evaluate(sha, workdir, pin_data=None, timeout=600):
    """Return {name: [rating, deviation, games]} for one commit, or an error."""
    tree = workdir / sha[:12]
    try:
        extract_tree(sha, tree, pin_data)
        driver = tree / "_rating_history_driver.py"
        driver.write_text(DRIVER)
        out_path = tree / "_out.json"
        proc = subprocess.run(
            # -S skips site-packages, so the project's own editable install
            # cannot answer `import coco_ratings` for a tree that predates the
            # src layout. The engine is dependency-free, so stdlib is enough.
            [sys.executable, "-S", "-E", str(driver), str(tree), str(out_path)],
            capture_output=True, timeout=timeout,
            env={**os.environ, "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if not out_path.exists():
            tail = (proc.stderr.decode(errors="replace") or "")[-500:]
            return {"ok": False, "error": f"driver produced no output: {tail}"}
        return json.loads(out_path.read_text())
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(tree, ignore_errors=True)


def diff_players(before, after):
    """Rating/deviation/games deltas between two replays."""
    names = sorted(set(before) | set(after))
    changed, added, removed = [], [], []
    for n in names:
        b, a = before.get(n), after.get(n)
        if b is None:
            added.append((n, a))
        elif a is None:
            removed.append((n, b))
        elif b[0] != a[0]:
            # name, rating before/after, deviation before/after, games before/after
            changed.append((n, b[0], a[0], b[1], a[1], b[2], a[2]))
    # Biggest absolute rating move first.
    changed.sort(key=lambda r: -abs((r[2] or 0) - (r[1] or 0)))
    return changed, added, removed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rev", default="HEAD", help="branch/rev to walk (default HEAD)")
    ap.add_argument("--since", help="only commits after this date (git --since)")
    ap.add_argument("--limit", type=int, help="only the N most recent .py commits")
    ap.add_argument("--commit", metavar="SHA",
                    help="report just this one commit, in full (implies a large --top)")
    ap.add_argument("--pin-data", metavar="REF",
                    help="overlay data/ and results/ from REF on every tree")
    ap.add_argument("--jobs", type=int, default=4, help="parallel replays (default 4)")
    ap.add_argument("-o", "--output", help="write the full report to this file")
    ap.add_argument("--json", help="also dump raw per-commit results here")
    ap.add_argument("--cache", help="reuse (and update) replays stored in this "
                                    "json file, so re-rendering costs nothing")
    ap.add_argument("--top", type=int, default=15,
                    help="players listed per changed commit (default 15)")
    args = ap.parse_args()

    if args.commit:
        commits = [git("rev-parse", args.commit).strip()]
        if args.top == ap.get_default("top"):
            args.top = 100000  # a single-commit report is never truncated
    else:
        rev_args = ["rev-list", args.rev]
        if args.since:
            rev_args.append(f"--since={args.since}")
        rev_args += ["--", "*.py"]
        commits = git(*rev_args).split()
        if args.limit:
            commits = commits[: args.limit]
        commits.reverse()  # oldest first

    pairs = []
    for sha in commits:
        try:
            parent = git("rev-parse", f"{sha}^").strip()
        except subprocess.CalledProcessError:
            continue  # root commit: nothing to compare against
        pairs.append((sha, parent))

    shas = sorted({s for pair in pairs for s in pair})

    cache = {}
    if args.cache and Path(args.cache).exists():
        stored = json.loads(Path(args.cache).read_text())
        cache = stored.get("results", stored)
        # A cached failure may just predate a driver fix, so retry those.
        cache = {k: v for k, v in cache.items() if v.get("ok")}
    todo = [s for s in shas if s not in cache]
    print(f"{len(pairs)} commits touch .py; {len(shas)} trees "
          f"({len(cache)} cached, {len(todo)} to replay, jobs={args.jobs})",
          file=sys.stderr)

    workdir = Path(tempfile.mkdtemp(prefix="rating-history-"))
    done, lock = 0, threading.Lock()

    def run(sha):
        nonlocal done
        res = evaluate(sha, workdir, args.pin_data)
        with lock:
            done += 1
            status = "ok" if res.get("ok") else "FAIL"
            print(f"  [{done}/{len(todo)}] {sha[:10]} {status}", file=sys.stderr)
        return sha, res

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            for sha, res in ex.map(run, todo):
                cache[sha] = res
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if args.cache:
        Path(args.cache).write_text(json.dumps({"results": cache}))

    report, failures, unchanged = [], [], 0
    for sha, parent in pairs:
        cur, prev = cache[sha], cache[parent]
        meta = commit_meta(sha)
        files = touched(sha)
        meta["touched_data"] = any(
            f.startswith(("data/", "results/")) for f in files
        )
        meta["py_files"] = [f for f in files if f.endswith(".py")]
        meta["kind"] = classify(sha)
        if not cur.get("ok") or not prev.get("ok"):
            failures.append((meta, prev.get("error"), cur.get("error")))
            continue
        changed, added, removed = diff_players(prev["players"], cur["players"])
        if not (changed or added or removed):
            unchanged += 1
            continue
        report.append((meta, changed, added, removed))

    out = render(report, failures, unchanged, len(pairs), args)
    print(out)
    if args.output:
        Path(args.output).write_text(out)
        print(f"\nwrote {args.output}", file=sys.stderr)
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"pairs": [{"sha": s, "parent": p} for s, p in pairs], "results": cache},
            indent=1))
        print(f"wrote {args.json}", file=sys.stderr)


def render(report, failures, unchanged, total, args):
    L = []
    add = L.append
    add("# Code changes that moved a rating\n")
    mode = f"data pinned at {args.pin_data}" if args.pin_data else "each tree as committed"
    add(f"{total} commits touched .py. {len(report)} changed someone's rating, "
        f"{unchanged} changed nothing, {len(failures)} could not be replayed. "
        f"Mode: {mode}.\n")

    engine = [r for r in report if r[0]["kind"] != "tournament-list"]
    listonly = [r for r in report if r[0]["kind"] == "tournament-list"]

    def table(rows):
        add("| date | commit | subject | players moved | biggest move | kind | data |")
        add("|---|---|---|---|---|---|---|")
        for meta, changed, added_p, removed_p in rows:
            moved = len(changed) + len(added_p) + len(removed_p)
            big = ""
            if changed:
                n, b, a = changed[0][:3]
                big = f"{n} {fmt(b)}→{fmt(a)}"
            elif added_p or removed_p:
                big = f"+{len(added_p)}/-{len(removed_p)} players"
            add(f"| {meta['date']} | `{meta['sha'][:10]}` | {meta['subject']} | {moved} "
                f"| {big} | {meta['kind']} | {'yes' if meta['touched_data'] else 'no'} |")

    add("## Engine changes that moved ratings\n")
    add("Commits whose Python diff is not purely the chronological tournament "
        f"list. This is the answer to the question — {len(engine)} of them.\n")
    table(engine)

    add("\n## Tournament-list edits\n")
    add("Until the list moved to data/tournaments.csv (`c5aa5ff05a`, 2025-11-16) "
        "it lived in all_rating.py, so adding a tournament was a .py change. "
        f"These {len(listonly)} commits move ratings because they add results, "
        "not because the maths changed.\n")
    table(listonly)

    add("\n## Detail: engine changes\n")
    for meta, changed, added_p, removed_p in engine:
        add(f"### `{meta['sha'][:10]}` {meta['subject']}")
        add(f"*{meta['date']} — {meta['author']}*  ")
        add(f"python files: {', '.join(meta['py_files']) or '(none in diff)'}  ")
        if meta["touched_data"]:
            add("**Also touched data/ or results/ — the change is not purely code.**  ")
        add("")
        if changed:
            add(f"{len(changed)} players' ratings changed"
                + (f" (showing {args.top})" if len(changed) > args.top else "") + ":\n")
            add("| player | before | after | delta | deviation | games |")
            add("|---|---|---|---|---|---|")
            for n, b, a, db, da, gb, ga in changed[: args.top]:
                d = (a or 0) - (b or 0)
                g = f"{gb}" if gb == ga else f"{gb}→{ga}"
                dev = fmt(db) if db == da else f"{fmt(db)}→{fmt(da)}"
                add(f"| {n} | {fmt(b)} | {fmt(a)} | {d:+.4g} | {dev} | {g} |")
            add("")
        if added_p:
            add(f"appeared: {', '.join(n for n, _ in added_p[:20])}"
                + (f" (+{len(added_p)-20} more)" if len(added_p) > 20 else "") + "\n")
        if removed_p:
            add(f"disappeared: {', '.join(n for n, _ in removed_p[:20])}"
                + (f" (+{len(removed_p)-20} more)" if len(removed_p) > 20 else "") + "\n")

    if failures:
        add("\n## Not replayable\n")
        add("These commits' trees could not produce a ratings list. The oldest "
            "predate the history replay entirely (no `process_old_results`).\n")
        add("| date | commit | subject | reason |")
        add("|---|---|---|---|")
        for meta, prev_err, cur_err in failures:
            why = (cur_err or prev_err or "").split("(")[0].strip()
            add(f"| {meta['date']} | `{meta['sha'][:10]}` | {meta['subject']} | {why} |")
    return "\n".join(L)


def fmt(v):
    if v is None:
        return "-"
    return f"{v:g}" if isinstance(v, float) else str(v)


if __name__ == "__main__":
    main()
