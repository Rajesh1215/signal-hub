"""Make sure the news is fresh before analysing. Step 1 of "analyze today".

    python3 engine/refresh.py               # collect first if the last collection is over 3 hours old
    python3 engine/refresh.py --max-age 0   # always collect now ("collect now")

Pulls the repo. If the data is too old, triggers the GitHub "collect" workflow
(it stays the only writer of collected data), waits for it to finish and pulls
again. If GitHub can't be reached, it says so and the analysis continues on the
data that is already there.
"""
import json
import subprocess
import sys
import time
from datetime import timedelta

from common import IST, ROOT, entity_dirs, now_utc, parse_time, read_json


def run(*cmd, timeout=120):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def pull():
    r = run("git", "pull", "-q", "--rebase", "--autostash")
    if r.returncode:
        print(f"! git pull failed: {r.stderr.strip()[:300]}")


def last_collect():
    times = [parse_time(h.get("last_run")) for e in entity_dirs()
             for h in read_json(e / "health.json", {}).values() if h.get("last_run")]
    return max(times) if times else None


def collect_on_github():
    started = now_utc()
    r = run("gh", "workflow", "run", "collect.yml")
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:300] or "gh workflow run failed")
    run_id = None
    for _ in range(24):  # find the run we just started (GitHub takes a few seconds to list it)
        time.sleep(5)
        out = run("gh", "run", "list", "--workflow", "collect.yml", "--limit", "1", "--json", "databaseId,createdAt")
        runs = json.loads(out.stdout or "[]")
        if runs and parse_time(runs[0]["createdAt"]) >= started - timedelta(seconds=60):
            run_id = runs[0]["databaseId"]
            break
    if not run_id:
        raise RuntimeError("started the collection but could not find its run")
    print(f"  collecting on GitHub (run {run_id}), usually 3-4 minutes…", flush=True)
    w = run("gh", "run", "watch", str(run_id), "--exit-status", "--interval", "15", timeout=1800)
    if w.returncode:
        raise RuntimeError(f"collection run {run_id} failed; see the Actions tab")


def main(argv):
    max_age = float(argv[argv.index("--max-age") + 1]) if "--max-age" in argv else 3
    pull()
    last = last_collect()
    age = (now_utc() - last).total_seconds() / 3600 if last else 999
    when = last.astimezone(IST).strftime("%d %b %H:%M IST") if last else "never"
    if age < max_age:
        print(f"News is fresh: last collected {age:.1f} h ago ({when}). Nothing to fetch.")
        return
    print(f"Last collected {when} ({age:.1f} h ago): fetching the latest news first.", flush=True)
    try:
        collect_on_github()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        print(f"! Could not run a fresh collection ({e}). Analysing the news already collected.")
        return
    pull()
    print(f"Fresh news collected at {last_collect().astimezone(IST):%d %b %H:%M IST}.")


if __name__ == "__main__":
    main(sys.argv[1:])
