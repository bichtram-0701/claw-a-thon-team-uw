"""Scheduled Jira -> Teams reminders. Team UW, Claw-a-thon 2026.

Run by the 'Teams reminders' GitHub Action (cron). Queries Jira and posts a
digest card to Teams. Runs on a GitHub runner because it can reach both
Atlassian Cloud and the Teams webhook (the dev sandbox cannot reach vngcloud).

Modes:
  overdue   - tasks past their due date and not Done           (09:00 reminder)
  due-soon  - tasks due tomorrow and not Done                  (17:00 reminder)
  stale     - tasks not updated in STALE_DAYS days, not Done   (nudge the owner)

Usage:  python scripts/jira_reminders.py <overdue|due-soon|stale>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jira_client as jc   # noqa: E402
import teams_client as tc  # noqa: E402


def run(mode: str) -> int:
    if mode == "overdue":
        issues = jc.overdue_issues()
        tc.digest_card("⚠️ Overdue tasks", issues,
                       empty_msg="No overdue tasks right now — nice!")
    elif mode == "due-soon":
        issues = jc.due_tomorrow_issues()
        tc.digest_card("⏰ Tasks due tomorrow", issues,
                       empty_msg="Nothing due tomorrow.", accent="Warning")
    elif mode == "stale":
        days = int(os.environ.get("STALE_DAYS", "7"))
        issues = jc.stale_issues(days)
        tc.digest_card(f"💤 Stale tasks (no update in {days}+ days) — please update",
                       issues, empty_msg=None, accent="Warning")
    else:
        print(f"unknown mode: {mode}", file=sys.stderr)
        return 2
    print(f"{mode}: {len(issues)} issue(s)")
    return 0


def main() -> int:
    if not jc.configured():
        print("Jira not configured (set ATLASSIAN_SITE/EMAIL/TOKEN).", file=sys.stderr)
        return 1
    if not tc.configured():
        print("Teams not configured (set TEAMS_WEBHOOK_URL).", file=sys.stderr)
        return 1
    modes = sys.argv[1:] or ["overdue"]
    rc = 0
    for m in modes:
        rc = run(m) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
