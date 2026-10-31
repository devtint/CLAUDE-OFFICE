# Claude Code hook for the Claude office. Claude Code runs it at moments the office cares about, so
# it knows at once instead of guessing from the transcripts:
#   SessionStart, SessionEnd        a Claude comes in or leaves through the portal (and its model)
#   PostModelSwitch                 the model changed (a /model switch or an automatic fallback)
#   PermissionRequest, Notification it needs you (the intercom); PermissionDenied: auto mode said no
#   Stop, StopFailure               the turn finished, or an API error ended it (like a usage limit)
#   PreCompact, PostCompact         the conversation is being compacted (a nap)
#   SubagentStart, SubagentStop     a helper starts or finishes
# It keeps one small file per session, merging each event into it, and prints nothing.
# Added to ~/.claude/settings.json by "install.py --hooks"; "install.py --uninstall-hooks" removes it.
import json
import os
import sys
import time

FOLDER = os.path.join(os.path.expanduser('~'), '.claude', 'office-hooks')
# events that say what the session is doing now; the others only add facts to the note
STATE_EVENTS = ('Notification', 'Stop', 'StopFailure', 'PermissionRequest', 'SessionStart')


def clip(v, n=200):
    return str(v or '')[:n]


def main():
    try:
        d = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(d, dict):
        return
    sid = ''.join(c for c in str(d.get('session_id') or '') if c.isalnum() or c in '-_')[:80]
    if not sid:
        return
    os.makedirs(FOLDER, exist_ok=True)
    path = os.path.join(FOLDER, sid + '.json')
    try:
        with open(path, encoding='utf-8') as fh:
            note = json.load(fh)
        if not isinstance(note, dict):
            note = {}
    except (OSError, ValueError):
        note = {}
    now = time.time()
    event = str(d.get('hook_event_name') or '')
    note['transcript'] = d.get('transcript_path') or note.get('transcript', '')
    agent = clip(d.get('agent_id'), 80)

    if event in STATE_EVENTS and not (agent and event in ('Stop', 'StopFailure')):
        note.update(event=event, type=clip(d.get('notification_type') or d.get('error') or d.get('source'), 60),
                    message=clip(d.get('message') or d.get('last_assistant_message') or d.get('error_details')),
                    tool=clip(d.get('tool_name'), 80), time=now)
    if event == 'SessionStart':
        note['started'] = now
        note.pop('ended', None)
        if d.get('session_title'):
            note['title'] = clip(d['session_title'], 120)
    elif event == 'SessionEnd':
        note['ended'] = now
        note['reason'] = clip(d.get('reason'), 40)
    elif event == 'PermissionDenied':
        note['denied'] = now
        note['denied_tool'] = clip(d.get('tool_name'), 80)
    elif event == 'PreCompact':
        note['compacting'] = now
    elif event == 'PostCompact':
        note['compacted'] = now
    elif event in ('SubagentStart', 'SubagentStop') and agent:
        agents = note.get('agents') if isinstance(note.get('agents'), dict) else {}
        a = agents.pop(agent, {})  # popped and put back, so the newest are last
        a['type'] = clip(d.get('agent_type'), 60) or a.get('type', '')
        a['stop' if event == 'SubagentStop' else 'start'] = now
        agents[agent] = a
        note['agents'] = dict(list(agents.items())[-40:])
    # SessionStart may name the model; PostModelSwitch always does
    model = d.get('to_model') if event == 'PostModelSwitch' else d.get('model') if event == 'SessionStart' else None
    if isinstance(model, dict):  # be kind to a future format
        model = model.get('id')
    if model:
        note['model'] = clip(model, 80)
        note['model_time'] = now

    tmp = f'{path}.{os.getpid()}.tmp'  # hooks can run side by side, so each writes its own
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(note, fh)
    os.replace(tmp, path)


if __name__ == '__main__':
    try:
        main()
    except Exception:  # a hook must never get in Claude Code's way
        pass
