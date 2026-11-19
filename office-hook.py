# Claude Code hook for the Claude office. Claude Code runs it when a session starts or ends, shows a
# notification (it needs your permission, or it is waiting for your input), finishes a turn or stops on
# an API error, and when a helper (subagent) starts or stops, so the office knows at once instead of
# guessing. It writes one small file per session (and one per helper) and prints nothing.
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

    def clean(v):
        return ''.join(c for c in str(v or '') if c.isalnum() or c in '-_')[:80]

    sid = clean(d.get('session_id'))
    if not sid:
        return
    os.makedirs(FOLDER, exist_ok=True)
    event = d.get('hook_event_name') or ''
    note = {
        'event': event,
        'type': d.get('notification_type') or d.get('error') or d.get('reason') or d.get('source') or '',
        'message': str(d.get('message') or d.get('error_details') or '')[:200],
        'transcript': d.get('transcript_path') or '',
        'model': d.get('model') or '',
        'time': time.time(),
    }
    name = sid
    if event in ('SubagentStart', 'SubagentStop'):
        aid = clean(d.get('agent_id'))
        aid = aid[len('agent-'):] if aid.startswith('agent-') else aid  # sent both ways
        if not aid:
            return
        name = sid + '.agent-' + aid  # a helper's note never replaces its session's
        note.update(agent_id=aid, agent_type=str(d.get('agent_type') or '')[:80],
                    agent_transcript=d.get('agent_transcript_path') or '')
    path = os.path.join(FOLDER, name + '.json')
    with open(path + '.tmp', 'w', encoding='utf-8') as fh:
        json.dump(note, fh)
    os.replace(path + '.tmp', path)


if __name__ == '__main__':
    try:
        main()
    except Exception:  # a hook must never get in Claude Code's way
        pass
