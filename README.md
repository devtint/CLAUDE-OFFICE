# Claude Office

A pixel open-plan office where every active [Claude Code](https://claude.com/claude-code) session
gets its own desk pod. The Claudes walk to the bookshelf to read, to the terminal rack to run
commands and to the whiteboard to think. They wait at their desk with "!" when they need you, and
take a coffee break in the lounge when a task is done.

It only reads the transcripts Claude Code already saves in `~/.claude/projects`. It never calls
Claude or any server, so **it costs no tokens and does not touch your usage limits.**

Works on **Windows, macOS and Linux**. It needs only Python 3.8+, with no packages to install.

![The office with three sessions](docs/office-wide.png)

## Features

- One desk pod per active session, on a rug in its model's colour: Opus orange, Sonnet blue,
  Haiku green, Fable purple. It shows the project, the state, the current step and how long it has run.
- The shared facilities along the back wall match the tools: bookshelf (reading files), search
  cabinet (grep and glob), tool rack (commands), whiteboard (thinking), calendar, mailbox,
  browser screen, web globe and design easel.
- Subagents sit at the spare desks of their session's pod while they work.
- States: working, thinking, may need you ("!"), fixing an error, done (coffee break, then the couch,
  a plant, a book or a little dance), idle (asleep at the desk).
- Hover a Claude for a card with its step, context use and steps in the last 10 minutes.
- Scales to any window and adds pod columns when it is wide.

<img src="docs/office.png" width="300" alt="The office in a narrow side panel">

## Let Claude set it up

Paste this into Claude Code (the terminal, the desktop app or an IDE) and it does the install for you:

```text
Please install Claude Office for me from https://github.com/devtint/CLAUDE-OFFICE

1. Check that Python 3.8 or newer and git are installed. If one is missing, tell me how to
   install it for my operating system and stop.
2. Clone the repository into my Claude Code skills folder:
   ~/.claude/skills/claude-office (on Windows: %USERPROFILE%\.claude\skills\claude-office).
   If that folder already exists, run "git pull" in it instead.
3. Read README.md and install.py before running anything, and tell me in one or two lines
   what they do.
4. Run install.py with Python from that folder to make the "Claude Office" and
   "Claude Office Off" desktop shortcuts.
5. Start the office with "open-office.pyw --server" and check that
   http://127.0.0.1:7788/state answers. If you are in the Claude desktop app, open
   http://127.0.0.1:7788 in the built-in browser panel.
6. Tell me how to open and stop it, and that from now on I can just say "start the office"
   or "stop the office".
```

Claude may ask for your OK before running commands. The office only reads your local session
files and never sends anything anywhere.

## Install

Or do it yourself. Clone it into your Claude Code skills folder, so Claude can open it for you too:

```bash
git clone https://github.com/devtint/CLAUDE-OFFICE ~/.claude/skills/claude-office
```

On Windows (PowerShell):

```powershell
git clone https://github.com/devtint/CLAUDE-OFFICE "$env:USERPROFILE\.claude\skills\claude-office"
```

Then make the two desktop shortcuts:

```bash
cd ~/.claude/skills/claude-office
python3 install.py        # on Windows: python install.py
```

| Shortcut | What it does |
|---|---|
| **Claude Office** | Starts the office if needed and opens it in a small app window |
| **Claude Office Off** | Stops it (the app window closes itself) |

On Windows they are `.lnk` files, on macOS `.app` bundles, and on Linux `.desktop` files. Run
`install.py` again if you move the folder, or `install.py --uninstall` to remove them.

The app window uses Edge, Chrome, Brave or Chromium, whichever it finds. Without one, the office
opens in your default browser.

**macOS:** the first time you open a shortcut, macOS may ask to confirm, because the app was made
on your Mac rather than downloaded. If it says Python is missing, run `xcode-select --install` or
install Python from python.org, then run `install.py` again.

## Use

- **Desktop:** double-click **Claude Office**.
- **Claude desktop app:** ask Claude to *"start the office"*. It opens in the built-in browser
  panel next to your chat. Say *"stop the office"* to close it.
- **Any browser:** start it with `python3 open-office.pyw --server`, then go to
  <http://127.0.0.1:7788>. Use `--stop` to stop it.

Other pages:

| Page | What it shows |
|---|---|
| `/?demo` | A made-up busy office, to try it without sessions running |
| `/rooms` | The older view, with one room per session |
| `/simple` | A plain strip of Claudes with a status list |

## How it works

- `tracker.py` reads the session transcripts once a second (only those changed in the last 36 hours)
  and works out each session's model, state, current tool and recent steps.
- `claude-office.py` is a small local server on `127.0.0.1:7788`. It serves the pages and `/state`
  (the sessions as JSON). It only listens on your own computer, and only one runs at a time.
- `workspace.html` draws the office on a canvas and polls `/state`.
- `open-office.pyw` is the launcher, and `install.py` makes the shortcuts.

If something goes wrong, the last error is kept in `office-error.log` next to the scripts.

## See also

[Claude Pet](https://github.com/devtint/claude-pet), an always-on-top desktop box with a pixel
Claude for each session.

## License

MIT
