"""Resolve rebase conflicts in JSON state files (seen.json, health.json…) by merging both sides.

Used by the collect workflow when two runs overlap. For every conflicted .json file:
dictionaries are merged key by key, lists are combined without duplicates, and for
plain values the version from the commit being replayed (this run) wins.

    python3 engine/merge_state.py     # then: git rebase --continue
Exits 1 if a conflicted file isn't JSON (needs a human).
"""
import json
import subprocess
import sys


def merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = merge(a[k], v) if k in a else v
        return out
    if isinstance(a, list) and isinstance(b, list):
        seen, out = set(), []
        for x in a + b:
            key = json.dumps(x, sort_keys=True)
            if key not in seen:
                seen.add(key)
                out.append(x)
        return out
    return b


def show(stage, path):
    r = subprocess.run(["git", "show", f":{stage}:{path}"], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def main():
    files = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], capture_output=True, text=True).stdout.split()
    for path in files:
        if not path.endswith(".json"):
            print(f"can't auto-merge {path}")
            sys.exit(1)
        upstream, ours = show(2, path), show(3, path)  # during a rebase: 2 = upstream, 3 = this run's commit
        merged = merge(upstream or {}, ours or {}) if (upstream is not None or ours is not None) else {}
        with open(path, "w") as f:
            f.write(json.dumps(merged, indent=1, ensure_ascii=False) + "\n")
        subprocess.run(["git", "add", path], check=True)
        print(f"merged {path}")


if __name__ == "__main__":
    main()
