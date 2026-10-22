# Claude office: one pixel room where every active Claude Code session is a Claude agent, served as
# a small web page for the Claude desktop app's side panel (or any browser).
# It only reads ~/.claude/projects (see tracker.py) and costs no tokens.
#   pythonw claude-office.py           start it, then open http://127.0.0.1:7788
#   pythonw claude-office.py --stop    stop it
# Pages: / the room, /?demo the room with made-up sessions.
# Only one runs at a time: a second start sees the port in use and exits.
import json
import os
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
                step = pet.step_text(tname, target, st == 'working')
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
            })
    return {'claudes': out, 'ready': tracker.ready}


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
        if self.path == '/state':
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
