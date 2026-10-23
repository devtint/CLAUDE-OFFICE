# Claude office: one pixel room where every active Claude Code session is a Claude agent, served as
# a small web page for the Claude desktop app's side panel (or any browser).
# It only reads ~/.claude/projects (see tracker.py) and costs no tokens.
#   pythonw claude-office.py           start it, then open http://127.0.0.1:7788
#   pythonw claude-office.py --stop    stop it
# Pages: / the room, /?demo the room with made-up sessions. /settings holds what the Pi on the shelf sets.
# The plant by the window keeps its growth in ~/.claude/office-plant.json.
# Only one runs at a time: a second start sees the port in use and exits.
import datetime
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tracker as pet  # noqa: E402

PORT = 7788
# / is the room; everything happens in that one page
PAGES = {'/': 'workspace.html'}
URL = f'http://127.0.0.1:{PORT}'


def state(tracker):
    """The active Claudes as plain data for the page."""
    now = time.time()
    with tracker.lock:
        claudes, newest = tracker.snapshot
        out = []
        for s in claudes:
            st, tool = s.status()
            name, colour = pet.model_info(s.model or (s.parent.model if s.parent else ''))
            step = ''
            if s.recent:
                ts, tname, target = s.recent[-1]
                step = pet.step_text(tname, target, st in ('working', 'waiting'))  # still open while it waits
            out.append({
                'id': s.path,
                'parent': s.parent.path if s.parent else '',
                'name': s.name(),
                'project': s.project,
                'colour': colour,
                'state': st,
                'word': pet.STATE_WORDS.get(st, st),
                'doing': pet.tool_word(tool) if tool else '',
                'step': step,
                'desc': s.desc,
                'turn': pet.ago(now - s.turn_start) if s.turn_start and st in ('working', 'thinking', 'waiting') else '',
                'steps': len(s.tools),
                'context': s.context_text(),
                'tool': tool,                                # the tool running now, for the office view
                'names': [r[1] for r in s.recent],           # recent tool names
                'kinds': dict(s.kinds),                      # every tool call so far, by kind
                'rate': sum(1 for t in s.tools if now - t < 600),  # steps in the last 10 minutes
                'newest': s is newest,
                # for the room: the task list, the latest edit and test, commits and pushes, and more
                'todos': s.todos[:8],
                'todo_age': round(now - s.todo_time) if s.todo_time else None,
                'edit': s.edit,
                'test': s.test,
                'test_age': round(now - s.test_time) if s.test_time else None,
                'commits': sum(1 for _, k in s.events if k == 'commit'),
                'pushes': sum(1 for _, k in s.events if k == 'push'),
                'compacted': round(now - s.compact_time) if s.compact_time else None,
                'background': sum(1 for b in s.background if now - b < 900),
                'streak': s.streak,
            })
        today = day_numbers(tracker.sessions.values())
    return {'claudes': out, 'ready': tracker.ready, 'today': today, 'plant': plant(today),
            'hooks': os.path.exists(pet.HOOKS_MARKER)}


PLANT_FILE = os.path.join(pet.HOME, '.claude', 'office-plant.json')
_plant = {'days': None, 'lock': threading.Lock()}


def plant(today):
    """The plant by the window grows with work: each day's points (a finished turn 1, a passing test
    run 1, a commit 2, a push 3) are kept for 30 days in ~/.claude/office-plant.json."""
    with _plant['lock']:
        days = _plant['days']
        if days is None:
            try:
                with open(PLANT_FILE, encoding='utf-8') as fh:
                    raw = json.load(fh).get('days', {})
                days = {k: int(v) for k, v in raw.items()
                        if re.fullmatch(r'\d{4}-\d\d-\d\d', str(k)) and isinstance(v, (int, float)) and v >= 0}
            except (OSError, ValueError, AttributeError):
                days = {}
            _plant['days'] = days
        key = time.strftime('%Y-%m-%d')
        points = today['done'] + today['pass'] + 2 * today['commit'] + 3 * today['push']
        if points > days.get(key, 0):  # today's sessions can drop out of the tracker, so keep the best count
            days[key] = points
            cutoff = time.strftime('%Y-%m-%d', time.localtime(time.time() - 30 * 86400))
            for k in [k for k in days if k < cutoff]:
                del days[k]
            try:
                with open(PLANT_FILE + '.tmp', 'w', encoding='utf-8') as fh:
                    json.dump({'days': days}, fh, indent=1)
                os.replace(PLANT_FILE + '.tmp', PLANT_FILE)
            except OSError:
                pass
        worked = [k for k, v in days.items() if v > 0]
        idle = (datetime.date.today() - datetime.date.fromisoformat(max(worked))).days if worked else None
        return {'total': sum(days.values()), 'today': days.get(key, 0), 'idle': idle}


def day_numbers(sessions):
    """Today's numbers across every session read: turns done, commits, pushes, tests, busiest model."""
    midnight = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    counts, steps = {'done': 0, 'commit': 0, 'push': 0, 'pass': 0, 'fail': 0}, {}
    for s in sessions:
        for ts, kind in s.events:
            if ts >= midnight and kind in counts:
                counts[kind] += 1
        n = sum(1 for ts in s.tools if ts >= midnight)
        if n:
            colour = pet.model_info(s.model or (s.parent.model if s.parent else ''))[1]
            steps[colour] = steps.get(colour, 0) + n
    counts['top'] = max(steps, key=steps.get) if steps else ''
    return counts


class Handler(BaseHTTPRequestHandler):
    tracker = None
    server_ref = None

    def send(self, body, kind):
        data = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.path = self.path.split('?', 1)[0]
        if self.path == '/settings':
            self.send(json.dumps(pet.settings()), 'application/json')
        elif self.path == '/state':
            self.send(json.dumps(state(self.tracker)), 'application/json')
        elif self.path == '/quit':
            self.send('bye', 'text/plain')
            threading.Thread(target=self.server_ref.shutdown, daemon=True).start()
        elif self.path in PAGES:
            page = PAGES[self.path]
            with open(os.path.join(HERE, page), encoding='utf-8') as fh:
                self.send(fh.read(), 'text/html; charset=utf-8')
        else:
            self.send_error(404)

    def do_POST(self):
        # settings from the room; JSON only, so another site cannot post here without asking first
        if self.path != '/settings' or 'application/json' not in (self.headers.get('Content-Type') or ''):
            self.send_error(404)
            return
        try:
            size = int(self.headers.get('Content-Length') or 0)
            data = json.loads(self.rfile.read(min(size, 4096)) or b'{}')
        except ValueError:
            self.send_error(400)
            return
        self.send(json.dumps(pet.save_settings(data)), 'application/json')

    def log_message(self, *args):
        pass


def running():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', PORT)) == 0


def main():
    if '--stop' in sys.argv:
        try:
            urllib.request.urlopen(URL + '/quit', timeout=2)
        except OSError:
            pass
        return
    if running():
        return
    tracker = pet.Tracker()
    tracker.start()
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    Handler.tracker, Handler.server_ref = tracker, server
    server.serve_forever()


if __name__ == '__main__':
    main()
