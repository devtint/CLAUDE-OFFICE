# Claude Office

A pixel room where every active [Claude Code](https://claude.com/claude-code) session is a little
3D Claude agent. Agents come in through a portal when a session starts and leave through it when the
session ends. They take one of the two computers to write code or run commands, read at the
bookshelf, browse on the laptop, wait with "!" when they need you, and spend their free time with
the office cat, the fish tank, a cup of tea and the view.

It only reads the transcripts Claude Code already saves in `~/.claude/projects`. It never calls
Claude, so **it costs no tokens and does not touch your usage limits.**

Works on **Windows, macOS and Linux**. It needs only Python 3.8+, with no packages to install.

![The room with three sessions](docs/office-wide.png)

## Features

- **One agent per session, in its model's colour:** Opus orange, Sonnet blue, Haiku green, Fable
  purple, other models grey. Helpers (subagents) are smaller Claudes in their session's colour, and
  their session goes to the portal to call them in.
- **Two computers** show what the agent at them is doing: `CODE` (Edit, Write) with code being
  typed, `RUN` (Bash) with a terminal and a progress bar, `FIX` after an error, and `DONE` when the
  task is finished. The title bar shows the project. When both are taken, the next agent waits by
  the tank with `<>` or `$` until one is free.
- **The intercom:** when a session needs your approval or asks you a question, its Claude goes to
  the intercom by the window, sits down with the handset and asks "OK?". The beacon flashes and the
  screen shows `ASK`; others who need you queue beside it. Tap the intercom to see what it is
  asking. Questions (`AskUserQuestion`) and plans to approve (`ExitPlanMode`) count straight away;
  any other step counts after it has waited 45 seconds.
- **The rest of the room:** reading files sends an agent to the bookshelf, web tools to the
  laptop and thinking shows `...`. Idle sessions sleep on the edge of the desk.
- **The laptop** counts the open tabs (sessions), with a dot for what each one is doing.
- **Free time** after a task: feed or tap the fish tank, pet the cat, sip tea, read a book,
  watch the sky (more often when it rains), stretch, dance or high-five another free agent.
- **A live window:** the clock, sun, moon (in its real phase), stars and city lights follow
  Bangkok time (UTC+7), and the sky follows the current Bangkok weather: rain, storms with
  lightning, fog and clouds.
- Hover or tap a Claude for its card: model, project, state, current step, turn time and context
  use. In a tall side panel the sessions are also listed under the room.
- Tap things: the cat purrs, the tank gets fed, the cup steams, the window gets a shooting star, the
  clock switches between 24 and 12 hours.

<img src="docs/office.png" width="300" alt="The room in a narrow side panel, with the session list">

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
files and never sends them anywhere.

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

Add these to the address to try things out:

| Option | What it does |
|---|---|
| `/?demo` | Made-up sessions that come and go, to try it without Claude Code running |
| `?hour=21` | Shows the sky at another time of day (Bangkok time) |
| `?weather=storm` | Shows a weather: `clear`, `cloudy`, `overcast`, `fog`, `rain`, `storm` or `snow` |
| `?noweather` | Turns off the weather request (see below) |

## How it works

- `tracker.py` reads the session transcripts once a second (only those changed in the last 36 hours)
  and works out each session's model, state, current tool and recent steps.
- `claude-office.py` is a small local server on `127.0.0.1:7788`. It serves the room and `/state`
  (the sessions as JSON). It only listens on your own computer, and only one runs at a time.
- `workspace.html` is the room: a 320x180 pixel canvas scaled up crisp, drawn in eight colours with
  a tiny 3D renderer for the agents and the cat. It polls `/state` every 1.5 seconds and turns each
  session's state and tool into what its agent does. All the animation, physics and free-time
  behaviour runs in the page.
- `open-office.pyw` is the launcher, and `install.py` makes the shortcuts.

The one request the page makes outside your computer is the Bangkok weather from
[Open-Meteo](https://open-meteo.com) (no key, no account, nothing about you or your sessions is
sent), every 10 minutes. Add `?noweather` to the address to turn it off.

If something goes wrong, the last error is kept in `office-error.log` next to the scripts.

## See also

[Claude Pet](https://github.com/devtint/claude-pet), an always-on-top desktop box with a pixel
Claude for each session.

## License

MIT
