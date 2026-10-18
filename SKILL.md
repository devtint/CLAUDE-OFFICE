---
name: claude-office
description: Start, show or stop the Claude office, a pixel open-plan office inside the Claude desktop app's side panel where every active Claude Code session has a desk pod. Use when the user says "start the office", "show the office", "open Claude office", "stop the office", "close the office", "mini pet" or "pet in the sidebar".
---

# Claude office

A pixel open-plan office shown in the Claude desktop app's built-in browser panel, shared by every
active Claude Code session. The back wall has the shared facilities (bookshelf, search cabinet, tool
rack, whiteboard, calendar, mailbox, browser screen, web globe, design easel) and the door. Each
session gets a desk pod on a rug in its model's colour (code desk and terminal, plus spare desks when
it is busy, where its helpers sit), labelled with the project, state and current step. The lounge at
the front has the huddle table, coffee and couches. Claudes walk through the aisles to the station
for the tool they are running, go to the whiteboard to think, wait at their desk with "!" when they
need the user, sleep at their desk when idle, and take a break when a task is done: coffee first,
then random things (couch, plant, reading, doodling, stretching, a little dance). The office scales
to the panel and adds pod columns when it is wide.

It runs a small local server that only reads the transcripts in `~/.claude/projects`, so it costs
no tokens while it runs. Only one server runs at a time, so the start command is always safe to run.

## Start or show

The launcher starts the server in the background and returns at once. Use the command for the OS.

Windows (PowerShell):

```powershell
Start-Process pythonw -ArgumentList ('"' + "$env:USERPROFILE\.claude\skills\claude-office\open-office.pyw" + '"'), '--server'
```

macOS or Linux (Bash):

```bash
python3 ~/.claude/skills/claude-office/open-office.pyw --server
```

Then open `http://127.0.0.1:7788` with the built-in browser's `preview_start` tool (`url` only, no
launch.json needed).

Other pages: `http://127.0.0.1:7788/?demo` (a made-up busy office), `/rooms` (the older view with
one room per session, also takes `?demo`) and `/simple` (a plain strip of Claudes with a status list).

## Stop

The same command with `--stop` in place of `--server`.

## Restart (after changing the files)

Run the stop command (in PowerShell add `-Wait`), then the start command, then reload the page.

Then reply in one short line, for example "The office is open in the side panel." Do not read the
scripts or explain how they work unless the user asks.

## Desktop shortcuts

`python install.py` in this folder (`python3` on macOS) makes two desktop shortcuts: `Claude Office`
starts the server if needed and opens the office in a small browser app window (Edge, Chrome, Brave
or Chromium), and `Claude Office Off` stops it. They are `.lnk` files on Windows, `.app` bundles on
macOS and `.desktop` files on Linux. Run it again if the shortcuts are lost or this folder moves;
`--uninstall` removes them. Office windows opened by the launcher (URL with `?app`) close themselves
when the server stops; the side panel keeps its last picture.

## Files

- `claude-office.py`: the local server (port 7788), `/state` gives the sessions as JSON.
- `tracker.py`: reads the transcripts (taken from the Claude Pet box so this skill stands alone).
- `open-office.pyw`: the launcher the shortcuts and the commands above use.
- `install.py`: makes or removes the desktop shortcuts. Icons are in `icons/`.
- `workspace.html`: the shared office (`/`). `office.html`: one room per session (`/rooms`).
  `mini.html`: the plain strip (`/simple`).
- Errors are kept in `office-error.log` next to the scripts.
