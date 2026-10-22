# Claude office: session tracker.
# Reads the Claude Code transcripts in ~/.claude/projects and keeps a live picture of each active
# session (model, state, current tool, recent steps) and its helpers (subagents).
# It never calls Claude or any server, so it costs no tokens.
# Taken from the Claude Pet box (claude-pet.pyw) so this skill works on its own.
import json
import os
import re
import threading
import time
import traceback
from collections import Counter, deque
from datetime import datetime

HOME = os.path.expanduser('~')
PROJECTS = os.path.join(HOME, '.claude', 'projects')
HERE = os.path.dirname(os.path.abspath(__file__))
ERROR_LOG = os.path.join(HERE, 'office-error.log')

ACTIVE_SECS = 10 * 60   # a session gets a Claude while its transcript changed in the last 10 min
DAY = 36 * 3600         # only transcripts changed this recently are read
WAIT_SECS = 45          # one step running this long: Claude may be waiting for you
MAX_PETS = 8          # the room has space for eight Claudes
MAX_HELPERS = 6

BG = '#1f1e1d'
PANEL = '#282624'
TEXT = '#f0eee6'
MUTED = '#a39e93'
FAINT = '#6f6a62'
LINE = '#3d3a36'
DARK = '#2b1d16'
CARD = '#33302d'
AMBER = '#e0a43a'
RED = '#e5484d'
MODEL_COLOURS = {
    'opus': '#D97757', 'sonnet': '#6A9BCC', 'haiku': '#7FA36B', 'fable': '#B08AD9',
}
OTHER_COLOUR = '#9a948a'
STATE_WORDS = {'working': 'Working', 'thinking': 'Thinking', 'waiting': 'May need you',
               'error': 'Fixing an error', 'done': 'Done', 'off': 'Idle'}

TOOL_WORDS = {
    'Bash': 'Running a command', 'PowerShell': 'Running a command',
    'Edit': 'Writing code', 'Write': 'Writing code', 'NotebookEdit': 'Writing code',
    'Read': 'Reading files', 'Grep': 'Searching the code', 'Glob': 'Looking for files',
    'WebSearch': 'Searching the web', 'WebFetch': 'Reading a web page',
    'SubagentHandback': 'Reporting back', 'ToolSearch': 'Loading tools', 'Skill': 'Using a skill',
    'Agent': 'Calling a helper', 'Task': 'Calling a helper', 'Artifact': 'Publishing a page',
    'AskUserQuestion': 'Asking you a question', 'ExitPlanMode': 'Waiting for you to approve a plan',
}
PAST_WORDS = {
    'Bash': 'Ran a command', 'PowerShell': 'Ran a command',
    'Edit': 'Edited', 'Write': 'Wrote', 'NotebookEdit': 'Edited', 'Read': 'Read',
    'Grep': 'Searched the code', 'Glob': 'Looked for files',
    'WebSearch': 'Searched the web', 'WebFetch': 'Read a web page',
    'Agent': 'Called a helper', 'Task': 'Called a helper', 'Artifact': 'Published a page',
    'SubagentHandback': 'Reported back', 'ToolSearch': 'Loaded tools', 'Skill': 'Used a skill',
    'AskUserQuestion': 'Asked you', 'ExitPlanMode': 'Shared a plan',
}
NO_COLON = ('Edit', 'Write', 'NotebookEdit', 'Read')  # 'Edited app.js', not 'Edited: app.js'
KINDS = {
    'Bash': 'Commands', 'PowerShell': 'Commands', 'Edit': 'Edits', 'Write': 'Edits', 'NotebookEdit': 'Edits',
    'Read': 'Reads', 'Grep': 'Searches', 'Glob': 'Searches', 'WebSearch': 'Web', 'WebFetch': 'Web',
    'Agent': 'Helpers', 'Task': 'Helpers',
}
# tools that stop and wait for you to answer, so the session needs you straight away
ASK_TOOLS = ('AskUserQuestion', 'ExitPlanMode')
# a transcript line worth parsing: a user or assistant message, compact or spaced JSON
MESSAGE_LINE = re.compile(rb'"type"\s*:\s*"(?:user|assistant)"')
# commands worth noticing: tests (pass or fail), commits and pushes
TEST_RE = re.compile(r'\b(pytest|py\.test|unittest|tox|nox|jest|vitest|mocha|rspec|phpunit|ctest|'
                     r'(npm|pnpm|yarn|bun)( run)? test|go test|cargo test|dotnet test|mvn test|gradle\w* test|'
                     r'swift test|mix test|deno test)\b')
COMMIT_RE = re.compile(r'\bgit\b[^|;&\n]*\bcommit\b')
PUSH_RE = re.compile(r'\bgit\b[^|;&\n]*\bpush\b')
# the office hooks (install.py --hooks) leave one small file per session here
HOOKS_DIR = os.path.join(HOME, '.claude', 'office-hooks')
HOOKS_MARKER = os.path.join(HOOKS_DIR, '.installed')
# helpers

def tool_word(name):
    if name in TOOL_WORDS:
        return TOOL_WORDS[name]
    if 'Browser' in name or 'chrome' in name:
        return 'Using the browser'
    return 'Using ' + name.split('__')[-1].replace('_', ' ')


def kind_of(name):
    if name in KINDS:
        return KINDS[name]
    if 'Browser' in name or 'chrome' in name:
        return 'Browser'
    return 'Other'


def model_info(model):
    """'claude-opus-5-5' -> ('Opus 5.5', colour)."""
    m = re.match(r'claude-([a-z]+)((?:-\d{1,2})*)', model or '')
    if not m:
        return 'Claude', OTHER_COLOUR
    family = m.group(1)
    version = '.'.join(p for p in m.group(2).split('-') if p)
    name = family.capitalize() + (' ' + version if version else '')
    return name, MODEL_COLOURS.get(family, OTHER_COLOUR)


def step_text(name, target, now):
    """A recent step: present tense while it runs ('Running a command: ...'), past tense after."""
    if now:
        verb = tool_word(name)
    elif name in PAST_WORDS:
        verb = PAST_WORDS[name]
    elif 'Browser' in name or 'chrome' in name:
        verb = 'Used the browser'
    else:
        verb = 'Used ' + name.split('__')[-1].replace('_', ' ')
    if not target:
        return verb
    return f'{verb} {target}' if name in NO_COLON and not now else f'{verb}: {target}'


def describe(name, inp):
    """(tool name, target) for the recent list, like ('Edit', 'app.js')."""
    target = ''
    path = inp.get('file_path') or inp.get('notebook_path') or inp.get('path')
    if path and name not in ('Grep', 'Glob'):
        target = os.path.basename(str(path).rstrip('/\\'))
    elif inp.get('description'):
        target = inp['description']
    elif isinstance(inp.get('questions'), list) and inp['questions'] and isinstance(inp['questions'][0], dict):
        target = inp['questions'][0].get('question') or ''  # AskUserQuestion: the first question
    elif inp.get('pattern'):
        target = inp['pattern']
    elif inp.get('query'):
        target = inp['query']
    elif inp.get('url'):
        target = re.sub(r'^https?://', '', inp['url'])
    return name, str(target)


def ago(secs):
    secs = int(max(0, secs))
    if secs < 60:
        return f'{secs}s'
    if secs < 3600:
        return f'{secs // 60}m {secs % 60:02d}s'
    return f'{secs // 3600}h {secs % 3600 // 60:02d}m'


def short(n):
    if n >= 1_000_000:
        return f'{n / 1_000_000:.1f}M'.replace('.0M', 'M')
    if n >= 1000:
        return f'{n / 1000:.0f}k'
    return str(int(n))


def hm(ts):
    return datetime.fromtimestamp(ts).strftime('%H:%M') if ts else ''


def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
    except (ValueError, AttributeError):
        return 0


# Claude Code names each project folder after its path with every other character turned into '-':
# C:\Users\me\code\app -> C--Users-me-code-app, /Users/me/code/app -> -Users-me-code-app
HOME_KEY = re.sub(r'[^A-Za-z0-9]', '-', HOME).lower()


def project_name(folder):
    low = folder.lower()
    if low == HOME_KEY:
        return 'Home'
    if 'scratch-workspaces' in low:  # a desktop app session started without a folder
        return 'No Folder'
    if low.startswith(HOME_KEY + '-'):
        name = folder[len(HOME_KEY) + 1:]
    else:
        name = folder.split('--', 1)[-1] if '--' in folder else folder
    return name.replace('-', ' ').strip().title() or folder


# reading the transcripts

class Session:
    def __init__(self, path, parent=None):
        self.path = path
        self.parent = parent  # the main Session, for a helper (subagent)
        self.project = parent.project if parent else project_name(os.path.basename(os.path.dirname(path)))
        self.label = ''       # helper type, like 'Explore'
        self.desc = ''        # helper task, from the Agent call
        self.agents = []      # Agent calls in this session: (time, description, type, call id)
        self.tool_id = ''     # for a helper: the id of the Agent call that started it
        # Agent calls that have reported back; helpers share their main session's set, so
        # helpers started by helpers finish too
        self.done_ids = parent.done_ids if parent else set()
        self.helper_mtime = 0  # for a main session: when one of its helpers last wrote
        self.offset = 0
        self.mtime = 0
        self.model = ''
        self.last = None
        self.started = 0
        self.turn_start = 0
        self.tools = []       # times of tool calls
        self.kinds = Counter()  # tool calls by kind, like 'Edits'
        self.files = {}       # edited file path -> last edit time
        self.errors = 0
        self.context = 0      # tokens Claude read on its latest reply: how full the context is
        self.peak_context = 0
        self.recent = deque(maxlen=14)  # (time, tool name, target)
        self.fake = None      # demo mode: a made-up (state, tool)
        self.todos = []       # the task list, from TodoWrite or the task tools: {'text', 'status'}
        self.todo_time = 0
        self.pending = {}     # tool call id -> 'test', 'commit' or 'push', until its result arrives
        self.events = []      # (time, kind) for today's numbers: done, commit, push, pass, fail
        self.test = ''        # the latest test run: 'pass' or 'fail'
        self.test_time = 0
        self.edit = None      # the latest edit: {'file', 'added', 'removed'}
        self.compact_time = 0  # when the conversation was last compacted
        self.background = []  # when background commands started
        self.streak = 0       # tool errors in a row
        self.hook = None      # the latest note from the office hook, if installed

    def update(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return
        self.mtime = st.st_mtime
        if st.st_size < self.offset:  # the file was rewritten: read it again
            self.__init__(self.path, self.parent)
            self.mtime = st.st_mtime
            if self.parent:
                read_meta(self)
        if st.st_size == self.offset:
            return
        with open(self.path, 'rb') as fh:
            fh.seek(self.offset)
            data = fh.read()
        end = data.rfind(b'\n')
        if end < 0:
            return
        self.offset += end + 1
        for line in data[:end].split(b'\n'):
            if b'<task-notification>' in line:
                # a background helper finished
                for tid, status in re.findall(rb'<tool-use-id>([^<]+)</tool-use-id>.*?<status>([a-z]+)</status>', line):
                    if status != b'running':
                        self.done_ids.add(tid.decode())
            if b'compact_boundary' in line:  # the conversation was compacted
                try:
                    self.compact_time = parse_ts(json.loads(line).get('timestamp')) or time.time()
                except ValueError:
                    pass
            if not MESSAGE_LINE.search(line):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get('type') not in ('user', 'assistant') or d.get('isMeta'):
                continue
            self.last = d
            msg = d.get('message') or {}
            ts = parse_ts(d.get('timestamp'))
            if ts and not self.started:
                self.started = ts
            content = msg.get('content')
            items = content if isinstance(content, list) else []
            if d['type'] == 'user':
                for x in items:
                    if x.get('type') == 'tool_result' and 'Async agent launched' not in str(x.get('content'))[:300]:
                        self.done_ids.add(x.get('tool_use_id'))
                    if x.get('type') == 'tool_result':
                        self.result(x, ts)
                if any(x.get('type') == 'tool_result' for x in items):
                    self.errors += sum(1 for x in items if x.get('type') == 'tool_result' and x.get('is_error'))
                else:
                    text = content if isinstance(content, str) else ' '.join(
                        x.get('text', '') for x in items if x.get('type') == 'text')
                    if text.strip() and not text.lstrip().startswith('<') and 'Request interrupted' not in text:
                        self.turn_start = ts
                continue
            usage = msg.get('usage')
            if usage and msg.get('model') != '<synthetic>':
                ctx = sum(usage.get(k) or 0 for k in (
                    'input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
                if ctx:
                    self.context = ctx
                    self.peak_context = max(self.peak_context, ctx)
            if msg.get('model') and msg['model'] != '<synthetic>':
                self.model = msg['model']
            if msg.get('stop_reason') == 'end_turn':
                self.events.append((ts, 'done'))
            for x in items:
                if x.get('type') != 'tool_use':
                    continue
                self.tools.append(ts)
                inp = x.get('input') or {}
                name = x.get('name', '')
                self.notice(name, inp, x.get('id'), ts)
                self.kinds[kind_of(name)] += 1
                path = inp.get('file_path') or inp.get('notebook_path')
                if path and name in ('Edit', 'Write', 'NotebookEdit'):
                    self.files[path] = ts
                if name in ('Agent', 'Task'):
                    self.agents.append((ts, inp.get('description') or '', inp.get('subagent_type') or '', x.get('id') or ''))
                self.recent.append((ts,) + describe(name, inp))

    def notice(self, name, inp, tid, ts):
        """Remembers what the office shows: the task list, edits, tests, commits, background jobs."""
        if name == 'TodoWrite' and isinstance(inp.get('todos'), list):
            self.todos = [{'text': str(t.get('content') or t.get('activeForm') or ''), 'status': str(t.get('status') or '')}
                          for t in inp['todos'] if isinstance(t, dict)][:12]
            self.todo_time = ts
        elif name == 'TaskCreate':
            self.todos = (self.todos + [{'text': str(inp.get('subject') or inp.get('description') or ''), 'status': 'pending'}])[-12:]
            self.todo_time = ts
        elif name == 'TaskUpdate' and str(inp.get('taskId', '')).isdigit():
            i = int(inp['taskId']) - 1
            if 0 <= i < len(self.todos) and inp.get('status'):
                self.todos[i]['status'] = str(inp['status'])
                self.todo_time = ts
        elif name in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
            edits = inp.get('edits') if isinstance(inp.get('edits'), list) else [inp]
            edits = [e for e in edits if isinstance(e, dict)]
            lines = lambda v: len(str(v).splitlines()) if v else 0
            path = inp.get('file_path') or inp.get('notebook_path') or ''
            self.edit = {'file': os.path.basename(str(path)),
                         'added': sum(lines(e.get('new_string') or e.get('content') or e.get('new_source')) for e in edits),
                         'removed': sum(lines(e.get('old_string')) for e in edits)}
        elif name in ('Bash', 'PowerShell'):
            cmd = str(inp.get('command') or '')
            kind = 'push' if PUSH_RE.search(cmd) else 'commit' if COMMIT_RE.search(cmd) else 'test' if TEST_RE.search(cmd) else ''
            if kind and tid:
                self.pending[tid] = kind
            if inp.get('run_in_background'):
                self.background.append(ts)

    def result(self, x, ts):
        """A tool result: counts error streaks and finishes tests, commits and pushes."""
        err = bool(x.get('is_error'))
        self.streak = self.streak + 1 if err else 0
        kind = self.pending.pop(x.get('tool_use_id'), '')
        if kind == 'test':
            self.test, self.test_time = ('fail' if err else 'pass'), ts
            self.events.append((ts, self.test))
        elif kind and not err:
            self.events.append((ts, kind))
        if len(self.events) > 400:
            self.events = self.events[-300:]

    @property
    def helper(self):
        return self.parent is not None

    def name(self):
        """'Opus 5.5' for a session, the helper type (like 'Explore') for a helper."""
        return (self.label or 'Helper') if self.helper else model_info(self.model)[0]

    def window(self):
        """The context window. Transcripts do not record it, so it is a best guess."""
        return 1_000_000 if self.peak_context > 200_000 or '1m' in self.model.lower() else 200_000

    def context_text(self):
        if not self.context:
            return ''
        w = self.window()
        return f'{self.context / w * 100:.0f}% ({short(self.context)} of {short(w)})'

    def status(self):
        """(state, tool). state: off, thinking, working, waiting, done, error."""
        if self.fake:
            return self.fake
        now = time.time()
        age = now - self.mtime
        d = self.last
        if self.helper and self.tool_id and self.tool_id in self.done_ids:
            return 'done', ''
        if not d or age > ACTIVE_SECS:
            return 'off', ''
        # the office hook knows for sure, as long as nothing was written after it
        h = self.hook
        if h and h.get('time', 0) >= self.mtime - 2:
            text = (str(h.get('type', '')) + ' ' + str(h.get('message', ''))).lower()
            if h.get('event') == 'Notification' and 'permission' in text:
                items = (d.get('message') or {}).get('content')
                tools = [x for x in (items if isinstance(items, list) else []) if x.get('type') == 'tool_use']
                return 'waiting', tools[-1].get('name', '') if tools else ''
            if h.get('event') == 'Stop' or 'waiting for your input' in text or 'idle' in text:
                return 'done', ''
        msg = d.get('message') or {}
        content = msg.get('content')
        if d['type'] == 'assistant':
            items = content if isinstance(content, list) else []
            tools = [x for x in items if x.get('type') == 'tool_use']
            if tools:
                name = tools[-1].get('name', '')
                if name in ASK_TOOLS:  # a question or a plan to approve: it needs you now
                    return 'waiting', name
                # waiting on its own helper is normal work, not waiting for you
                busy_helper = name in ('Agent', 'Task') or now - self.helper_mtime < 30
                # with the hooks installed a permission prompt is reported exactly, so a long step is just work;
                # a helper's long step is work too (a prompt it raises shows up on its main session)
                guess = (age > WAIT_SECS and not busy_helper and not self.helper
                         and not os.path.exists(HOOKS_MARKER))
                return ('waiting' if guess else 'working'), name
            if msg.get('stop_reason') == 'end_turn':
                return 'done', ''
            return ('thinking' if age < 180 else 'off'), ''
        if isinstance(content, str):
            text = content
        else:
            items = content if isinstance(content, list) else []
            if any(x.get('type') == 'tool_result' and x.get('is_error') for x in items):
                return ('error' if age < 120 else 'off'), ''
            text = ' '.join(x.get('text', '') for x in items if x.get('type') == 'text')
        if 'Request interrupted' in text:
            return 'done', ''
        return ('thinking' if age < 180 else 'off'), ''


def read_meta(s):
    """agent-<id>.meta.json next to a helper transcript holds its type, task and Agent call id."""
    meta = s.path[:-len('.jsonl')] + '.meta.json'
    try:
        with open(meta, encoding='utf-8') as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return
    s.label = d.get('agentType') or d.get('subagent_type') or d.get('type') or s.label
    s.desc = d.get('description') or s.desc
    s.tool_id = d.get('toolUseId') or s.tool_id


def parent_id(path):
    """The session a loose helper transcript belongs to, from the sessionId on its first lines."""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(8192)
    except OSError:
        return ''
    m = re.search(rb'"sessionId"\s*:\s*"([0-9A-Za-z_-]+)"', head)
    return m.group(1).decode() if m else ''


class Tracker(threading.Thread):
    """Background thread: keeps the sessions up to date. Hold self.lock to read them."""

    def __init__(self):
        super().__init__(daemon=True)
        self.lock = threading.Lock()
        self.sessions = {}
        self.snapshot = ([], None)  # (active Claudes: sessions then helpers, the newest session)
        self.ready = False

    def run(self):
        while True:
            try:
                self.scan()
            except Exception:
                log_error()
            self.ready = True
            time.sleep(1)

    def scan(self):
        now = time.time()
        try:
            folders = [d.path for d in os.scandir(PROJECTS) if d.is_dir()]
        except OSError:
            folders = []
        for folder in folders:
            try:
                files = [f for f in os.scandir(folder) if f.name.endswith('.jsonl')]
            except OSError:
                continue
            loose = {}  # older Claude Code keeps helper transcripts (agent-*.jsonl) beside the sessions
            for f in files:
                try:
                    if now - f.stat().st_mtime > DAY:
                        continue
                    if f.name.startswith('agent-'):
                        parent = parent_id(f.path)
                        if parent:
                            loose.setdefault(os.path.join(folder, parent + '.jsonl'), []).append(f.path)
                        continue
                    with self.lock:
                        s = self.sessions.get(f.path)
                        if not s:
                            s = self.sessions[f.path] = Session(f.path)
                        s.update()
                        if now - s.mtime < ACTIVE_SECS:
                            self.scan_helpers(s, now, loose.get(f.path, []))
                except Exception:
                    log_error()
        self.read_hooks(now)
        with self.lock:
            mains = sorted((s for s in self.sessions.values() if not s.helper), key=lambda s: -s.mtime)
            active = [s for s in mains if now - s.mtime < ACTIVE_SECS][:MAX_PETS]
            helpers = []
            for s in self.sessions.values():
                if s.helper and s.parent in active:
                    # a helper stays while it works, and a few seconds after it finishes
                    if s.status()[0] == 'done':
                        s.done_at = getattr(s, 'done_at', 0) or (now if now - s.mtime < 60 else 1)
                        if now - s.done_at < 15:
                            helpers.append(s)
                    elif now - s.mtime < 300:
                        helpers.append(s)
            helpers.sort(key=lambda s: s.started)
            self.snapshot = (active + helpers[:MAX_HELPERS], mains[0] if mains else None)

    def read_hooks(self, now):
        """Notes from the office hook: one small file per session; day-old ones are tidied away."""
        try:
            files = [f for f in os.scandir(HOOKS_DIR) if f.name.endswith('.json')]
        except OSError:
            return
        with self.lock:
            by_path = {os.path.normcase(os.path.abspath(p)): s for p, s in self.sessions.items()}
        for f in files:
            try:
                if now - f.stat().st_mtime > DAY:
                    os.remove(f.path)
                    continue
                with open(f.path, encoding='utf-8') as fh:
                    note = json.load(fh)
            except (OSError, ValueError):
                continue
            s = by_path.get(os.path.normcase(os.path.abspath(str(note.get('transcript') or ''))))
            if s:
                with self.lock:
                    s.hook = note

    def scan_helpers(self, main, now, loose=()):
        """Subagent transcripts live in a folder named after the session (older versions: beside it)."""
        folder = main.path[:-len('.jsonl')]
        found = list(loose)
        for root, _, names in os.walk(folder):
            for n in names:
                if n.endswith('.jsonl'):
                    found.append(os.path.join(root, n))
        if not found:
            return
        new = False
        for p in found:
            s = self.sessions.get(p)
            if not s:
                try:
                    if now - os.stat(p).st_mtime > DAY:
                        continue
                except OSError:
                    continue
                s = self.sessions[p] = Session(p, main)
                new = True
                read_meta(s)
            s.update()
            main.helper_mtime = max(main.helper_mtime, s.mtime)
        if new or any(not self.sessions[p].label for p in found if p in self.sessions):
            # without a meta file, match helpers to the session's Agent calls in the order they started
            mine = sorted((s for s in self.sessions.values() if s.parent is main and s.started),
                          key=lambda s: s.started)
            for s, (_, desc, kind, tid) in zip(mine, main.agents):
                s.desc = s.desc or desc
                s.tool_id = s.tool_id or tid
                s.label = s.label or kind or 'Helper'
            for s in mine:
                s.label = s.label or 'Helper'


def log_error():
    """Keeps the last error in pet-error.log, so a problem can be found without stopping the box."""
    try:
        with open(ERROR_LOG, 'w', encoding='utf-8') as fh:
            fh.write(datetime.now().isoformat() + '\n' + traceback.format_exc())
    except OSError:
        pass
