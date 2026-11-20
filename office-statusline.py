# Claude Code status line for the Claude office. Claude Code hands a status line its session as JSON
# on stdin, and that JSON is the only place the plan limits appear on this computer: how much of the
# 5 hour window and of the week is used, and when each one resets. This writes those four numbers to
# ~/.claude/office-usage.json for the two hourglasses on the shelf, and then prints your own status
# line, unchanged, so nothing about your prompt moves.
#
# Added to ~/.claude/settings.json by "install.py --statusline", which also remembers the status line
# you already had in ~/.claude/office-statusline.json and runs it from here;
# "install.py --uninstall-statusline" puts it back as it was.
#
# Nothing is sent anywhere: the file stays on this computer, and the office reads it from there.
import json
import os
import subprocess
import sys
import time

HOME = os.path.expanduser('~')
USAGE = os.path.join(HOME, '.claude', 'office-usage.json')
CHAIN = os.path.join(HOME, '.claude', 'office-statusline.json')


def window(d):
    """One limit window from the status line JSON: how much is used, and when it resets."""
    if not isinstance(d, dict):
        return None
    try:
        pct = float(d.get('used_percentage'))
    except (TypeError, ValueError):
        return None
    out = {'pct': max(0.0, min(100.0, pct))}
    try:
        resets = int(d.get('resets_at'))
        if resets > 0:
            out['resets'] = resets
    except (TypeError, ValueError):
        pass
    return out


def save(payload):
    """Keeps the two windows in ~/.claude/office-usage.json, written whole so a reader never sees half."""
    limits = payload.get('rate_limits') if isinstance(payload, dict) else None
    if not isinstance(limits, dict):
        return
    now = time.time()
    out = {'time': now}
    for key, name in (('five_hour', 'five'), ('seven_day', 'seven')):
        got = window(limits.get(key))
        if got:
            out[name] = got
    if 'five' not in out and 'seven' not in out:
        return  # no limits in this payload (an API key, say): leave what is already there
    try:  # a payload with only one of the two keeps the other, as long as its window has not reset
        with open(USAGE, encoding='utf-8') as fh:
            before = json.load(fh)
        for name in ('five', 'seven'):
            old = before.get(name)
            if name not in out and isinstance(old, dict) and old.get('resets', 0) > now:
                out[name] = old
    except (OSError, ValueError, AttributeError):
        pass
    tmp = '%s.%d.tmp' % (USAGE, os.getpid())  # every session writes this file, so each uses its own
    try:
        os.makedirs(os.path.dirname(USAGE), exist_ok=True)
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(out, fh)
        os.replace(tmp, USAGE)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def chained():
    """The status line you had before the office took the slot, if there is one."""
    try:
        with open(CHAIN, encoding='utf-8') as fh:
            cmd = json.load(fh).get('chain')
    except (OSError, ValueError, AttributeError):
        return None
    return cmd if isinstance(cmd, str) and cmd.strip() else None


def plain(payload):
    """What the office prints when it has the status line to itself: the two limits, shortest form."""
    limits = payload.get('rate_limits') if isinstance(payload, dict) else {}
    bits = []
    for key, name in (('five_hour', '5h'), ('seven_day', '7d')):
        got = window((limits or {}).get(key))
        if got:
            bits.append('%s %d%%' % (name, round(got['pct'])))
    return '  '.join(bits)


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {}
    save(payload)

    cmd = chained()
    if not cmd:
        sys.stdout.write(plain(payload))
        return
    try:  # your own status line, run exactly as Claude Code would have run it, with the same input
        done = subprocess.run(cmd, shell=True, input=raw, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=10,
                              universal_newlines=True, cwd=(payload.get('cwd') or None))
        sys.stdout.write(done.stdout or '')
    except (OSError, subprocess.SubprocessError):
        sys.stdout.write(plain(payload))


if __name__ == '__main__':
    try:
        main()
    except Exception:  # a status line must never get in Claude Code's way
        pass
