---
name: claude-office
description: Start, show or stop the Claude office, a pixel room inside the Claude desktop app's side panel where every active Claude Code session is a little Claude agent. Use when the user says "start the office", "show the office", "open Claude office", "stop the office", "close the office", "mini pet" or "pet in the sidebar".
---

# Claude office

A pixel room shown in the Claude desktop app's built-in browser panel, where every active Claude
Code session is a little 3D Claude agent. Agents arrive through a portal when a session starts and
leave through it when it ends. They use the two computers to write code (CODE) and run commands
(RUN), show FIX after an error and DONE when finished, read at the bookshelf, browse on the laptop,
go to the intercom to ask the user when they need approval or have a question, and sleep on the
desk when idle. In free time they feed the
fish, pet the cat, sip tea, read, watch the sky or high-five each other. The laptop counts the open
tabs (sessions). The clock and the window follow the room's time zone and city weather (Bangkok by
default). Tapping the Raspberry Pi on the shelf opens the settings: time zone, weather city, units,
alerts, how long idle sessions stay, how many Claudes fit, subagents and calm mode. They are saved
in `~/.claude/office-settings.json`. In a tall panel the sessions are listed under the room.

It runs a small local server that only reads the transcripts in `~/.claude/projects`, so it costs
no tokens while it runs. The page's only outside requests are the weather from Open-Meteo and a
city search when the user presses FIND in the settings (weather can be turned off there, or with
`?noweather`). Only one server runs at a time, so the start command is always
safe to run.

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

To try it without sessions: `http://127.0.0.1:7788/?demo` (made-up sessions that come and go).

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

- `claude-office.py`: the local server (port 7788), `/state` gives the sessions as JSON, `/settings`
  reads and saves the settings.
- `tracker.py`: reads the transcripts (taken from the Claude Pet box so this skill stands alone).
- `office-hook.py`: the optional Claude Code hook; `python install.py --hooks` adds it, `--uninstall-hooks`
  removes it. With it, permission prompts and finished turns show in the room at once.
- `open-office.pyw`: the launcher the shortcuts and the commands above use.
- `install.py`: makes or removes the desktop shortcuts. Icons are in `icons/`.
- `workspace.html`: the room (`/`), the only page.
- Errors are kept in `office-error.log` next to the scripts.
