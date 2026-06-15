"""Poll Jira for new/changed issues and post Teams cards. Team UW.

Runs on a GitHub Actions cron (every ~2 min). For each issue updated within the
look-back window it posts: a "new task" card (issue just created) or a "task
updated" card (changed fields in red, old -> new). Dedupe via a small state file
(issue key -> last-notified 'updated' timestamp) persisted with actions/cache, so
overlapping windows never double-notify.

Cold start (no state): record a baseline silently — don't flood the channel.

Env: ATLASSIAN_*, TEAMS_WEBHOOK_URL, POLL_WINDOW_MIN (default 20),
     POLL_STATE_FILE (default .poll_state/state.json), CREATE_GRACE_SEC (120).
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jira_client as jc   # noqa: E402
import teams_client as tc  # noqa: E402

WINDOW_MIN = int(os.environ.get("POLL_WINDOW_MIN", "720"))   # how far back to fetch
RECENT_MIN = int(os.environ.get("POLL_RECENT_MIN", "45"))    # cold-start notify cutoff
STATE_FILE = os.environ.get("POLL_STATE_FILE", ".poll_state/state.json")


def _load() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def _save(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def _dt(s):
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    if not jc.configured() or not tc.configured():
        print("Missing ATLASSIAN_* or TEAMS_WEBHOOK_URL", file=sys.stderr)
        return 1

    state = _load()
    seen = state.get("seen", {})
    now = dt.datetime.now(dt.timezone.utc)
    last_run = _dt(state.get("last_run")) if state.get("last_run") else None
    # Notify anything changed at/after this cutoff; older items are baselined
    # silently. Warm runs use last_run (never miss); cold runs use a short
    # recency so a fresh start still reports very recent tasks without spamming
    # history.
    cutoff = last_run or (now - dt.timedelta(minutes=RECENT_MIN))

    issues = jc.search(f"updated >= -{WINDOW_MIN}m ORDER BY updated ASC", limit=200)
    notified = 0
    for it in issues:
        key, upd, created = it.get("key"), it.get("updated"), it.get("created")
        if seen.get(key) == upd:
            continue  # already handled this exact version
        seen[key] = upd
        uu, cu = _dt(upd), _dt(created)
        if not uu or uu < cutoff:
            continue  # old change / baseline — record silently, don't notify
        is_new = cu is not None and cu >= cutoff
        full = jc.get_issue_full(key)
        if is_new:
            tc.issue_card(full, header="New task created")
        else:
            tc.change_card(full, jc.get_latest_changes(key), header="Task updated")
        notified += 1

    if len(seen) > 1000:
        seen = dict(list(seen.items())[-1000:])
    _save({"seen": seen, "last_run": now.isoformat()})
    print(f"polled {len(issues)} issue(s); {notified} card(s) sent; cutoff={cutoff.isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
