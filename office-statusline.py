# Status line for the Claude office. Claude Code runs the status line after each change in a
# session and hands it facts the transcripts do not have: how full the context window is (as a
# percentage), the 5-hour and weekly usage limits, the session's name, the model, the effort level.
# This saves those facts for the office in one small file per session, then runs the status line
# you had before (saved by install.py) and shows what it prints, so your own status line stays as
# it was. Without one, it prints a short line of its own: the model and how full the context is.
# Set up by "install.py --statusline"; "install.py --uninstall-statusline" puts yours back.
import json
import os
import shutil
import subprocess
import sys
import time

FOLDER = os.path.join(os.path.expanduser('~'), '.claude', 'office-hooks')
# outside the hooks folder, whose day-old files the office tidies away
ORIGINAL = os.path.join(os.path.expanduser('~'), '.claude', 'office-statusline-original.json')


def pick(d, *keys):
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def save(d):
    sid = ''.join(c for c in str(d.get('session_id') or '') if c.isalnum() or c in '-_')[:80]
    if not sid:
        return
    limits = {}
    for name in ('five_hour', 'seven_day'):
        w = pick(d, 'rate_limits', name)
        if isinstance(w, dict) and isinstance(w.get('used_percentage'), (int, float)):
            limits[name] = {'used': w['used_percentage'], 'resets': w.get('resets_at')}
    note = {
        'transcript': d.get('transcript_path') or '',
        'time': time.time(),
        'model': str(pick(d, 'model', 'id') or '')[:80],
        'model_name': str(pick(d, 'model', 'display_name') or '')[:40],
        'title': str(d.get('session_name') or '')[:120],
        'context_pct': pick(d, 'context_window', 'used_percentage'),
        'context_size': pick(d, 'context_window', 'context_window_size'),
        'effort': str(pick(d, 'effort', 'level') or '')[:10],
        'thinking': bool(pick(d, 'thinking', 'enabled')),
        'branch': str(pick(d, 'worktree', 'branch') or pick(d, 'workspace', 'git_worktree') or '')[:80],
        'limits': limits,
    }
    os.makedirs(FOLDER, exist_ok=True)
    path = os.path.join(FOLDER, sid + '.status.json')
    tmp = f'{path}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(note, fh)
    os.replace(tmp, path)


def original_command():
    try:
        with open(ORIGINAL, encoding='utf-8') as fh:
            line = json.load(fh).get('statusLine') or {}
    except (OSError, ValueError, AttributeError):
        return ''
    cmd = line.get('command') if isinstance(line, dict) else ''
    return cmd if isinstance(cmd, str) and 'office-statusline.py' not in cmd else ''


def run_original(cmd, raw):
    """Runs your own status line with the same input and passes on what it prints."""
    if os.name == 'nt' and shutil.which('bash'):  # Claude Code runs status lines with Git Bash on Windows
        args, shell = ['bash', '-c', cmd], False
    else:
        args, shell = cmd, True
    out = subprocess.run(args, shell=shell, input=raw, stdout=subprocess.PIPE, timeout=30).stdout
    sys.stdout.buffer.write(out)


def main():
    raw = sys.stdin.buffer.read()
    try:
        d = json.loads(raw.decode('utf-8', 'replace'))
    except ValueError:
        d = {}
    if isinstance(d, dict):
        try:
            save(d)
        except Exception:  # never let the office break the status line
            pass
    else:
        d = {}
    cmd = original_command()
    if cmd:
        run_original(cmd, raw)
        return
    name = pick(d, 'model', 'display_name') or ''
    pct = pick(d, 'context_window', 'used_percentage')
    parts = [str(name)] if name else []
    if isinstance(pct, (int, float)):
        parts.append(f'{round(pct)}% context')
    print('  '.join(parts))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
