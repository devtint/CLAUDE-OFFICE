# Claude Code hook for the Claude office. Claude Code runs it when a session shows a notification
# (it needs your permission, or it is waiting for your input) and when a turn finishes, so the office
# knows at once instead of guessing. It writes one small file per session and prints nothing.
# Added to ~/.claude/settings.json by "install.py --hooks"; "install.py --uninstall-hooks" removes it.
import json
import os
import sys
import time

FOLDER = os.path.join(os.path.expanduser('~'), '.claude', 'office-hooks')


def main():
    try:
        d = json.load(sys.stdin)
    except ValueError:
        return
    sid = ''.join(c for c in str(d.get('session_id') or '') if c.isalnum() or c in '-_')[:80]
    if not sid:
        return
    os.makedirs(FOLDER, exist_ok=True)
    note = {
        'event': d.get('hook_event_name') or '',
        'type': d.get('notification_type') or '',
        'message': str(d.get('message') or '')[:200],
        'transcript': d.get('transcript_path') or '',
        'time': time.time(),
    }
    path = os.path.join(FOLDER, sid + '.json')
    with open(path + '.tmp', 'w', encoding='utf-8') as fh:
        json.dump(note, fh)
    os.replace(path + '.tmp', path)


if __name__ == '__main__':
    try:
        main()
    except Exception:  # a hook must never get in Claude Code's way
        pass
