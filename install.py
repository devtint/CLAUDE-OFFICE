# Makes the two desktop shortcuts for the Claude office: "Claude Office" (start and open) and
# "Claude Office Off" (stop). Works out every path when it runs, so it suits any computer.
#   python install.py               make the shortcuts (Windows .lnk, macOS .app, Linux .desktop)
#   python install.py --uninstall   remove them (and the full screen window's browser profile)
#   python install.py --hooks       add the office hooks to Claude Code (exact "needs you" and "done")
#   python install.py --uninstall-hooks   remove the hooks again
#   python install.py --statusline  let the office read the status line (context %, usage limits, names);
#                                   your own status line keeps showing as before
#   python install.py --uninstall-statusline   put your own status line back
# Run it again after moving this folder.
import json
import os
import plistlib
import shutil
import stat
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(HERE, 'open-office.pyw')
SHORTCUTS = [  # name, launcher argument, icon
    ('Claude Office', '', 'office'),
    ('Claude Office Off', '--stop', 'office-off'),
]


def desktop():
    """The desktop folder, including one moved by OneDrive on Windows or by XDG on Linux."""
    if os.name == 'nt':
        try:
            out = subprocess.run(['powershell', '-NoProfile', '-Command',
                                  '[Environment]::GetFolderPath("Desktop")'],
                                 capture_output=True, text=True, timeout=20).stdout.strip()
            if out and os.path.isdir(out):
                return out
        except OSError:
            pass
    elif sys.platform != 'darwin':
        try:
            out = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True).stdout.strip()
            if out and os.path.isdir(out):
                return out
        except OSError:
            pass
    return os.path.join(os.path.expanduser('~'), 'Desktop')


def ps_quote(s):
    return "'" + s.replace("'", "''") + "'"


def windows(folder, remove):
    py = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    py = py if os.path.exists(py) else sys.executable
    for name, arg, icon in SHORTCUTS:
        path = os.path.join(folder, name + '.lnk')
        if remove:
            if os.path.exists(path):
                os.remove(path)
            continue
        args = f'"{LAUNCHER}"' + (f' {arg}' if arg else '')
        script = (f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut({ps_quote(path)});'
                  f'$s.TargetPath={ps_quote(py)};$s.Arguments={ps_quote(args)};'
                  f'$s.WorkingDirectory={ps_quote(HERE)};'
                  f'$s.IconLocation={ps_quote(os.path.join(HERE, "icons", icon + ".ico") + ",0")};$s.Save()')
        subprocess.run(['powershell', '-NoProfile', '-Command', script], check=True)
        print('made', path)


def mac(folder, remove):
    for name, arg, icon in SHORTCUTS:
        app = os.path.join(folder, name + '.app')
        if os.path.exists(app):
            shutil.rmtree(app)
        if remove:
            continue
        macos = os.path.join(app, 'Contents', 'MacOS')
        res = os.path.join(app, 'Contents', 'Resources')
        os.makedirs(macos)
        os.makedirs(res)
        run = os.path.join(macos, 'run')
        with open(run, 'w', encoding='utf-8') as fh:
            fh.write('#!/bin/sh\n')
            fh.write(f'exec "{sys.executable}" "{LAUNCHER}"{" " + arg if arg else ""}\n')
        os.chmod(run, os.stat(run).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        info = {
            'CFBundleName': name, 'CFBundleDisplayName': name, 'CFBundleExecutable': 'run',
            'CFBundleIdentifier': 'local.claude-office.' + icon, 'CFBundlePackageType': 'APPL',
            'CFBundleVersion': '1.0', 'LSUIElement': True,  # no Dock icon for the launcher itself
        }
        png = os.path.join(HERE, 'icons', icon + '.png')
        icns = os.path.join(res, 'icon.icns')
        try:  # sips ships with macOS and turns the PNG into an app icon
            subprocess.run(['sips', '-s', 'format', 'icns', png, '--out', icns],
                           check=True, capture_output=True)
            info['CFBundleIconFile'] = 'icon'
        except (OSError, subprocess.CalledProcessError):
            pass
        with open(os.path.join(app, 'Contents', 'Info.plist'), 'wb') as fh:
            plistlib.dump(info, fh)
        print('made', app)


def linux(folder, remove):
    for name, arg, icon in SHORTCUTS:
        path = os.path.join(folder, name.replace(' ', '-').lower() + '.desktop')
        if remove:
            if os.path.exists(path):
                os.remove(path)
            continue
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('[Desktop Entry]\nType=Application\n'
                     f'Name={name}\n'
                     f'Exec="{sys.executable}" "{LAUNCHER}"{" " + arg if arg else ""}\n'
                     f'Icon={os.path.join(HERE, "icons", icon + ".png")}\nTerminal=false\n')
        os.chmod(path, 0o755)
        print('made', path)


# ---------- Claude Code hooks ----------
# The hook runs at the moments the office cares about (see office-hook.py): a session starting or
# ending, a permission prompt, a turn finishing or failing, a model switch, compaction, helpers.
# It writes a tiny file the tracker reads; it never calls Claude, so it costs no tokens.

SETTINGS = os.path.join(os.path.expanduser('~'), '.claude', 'settings.json')
HOOK_SCRIPT = os.path.join(HERE, 'office-hook.py')
HOOK_EVENTS = ('Notification', 'Stop', 'StopFailure', 'SessionStart', 'SessionEnd', 'PostModelSwitch',
               'PermissionRequest', 'PermissionDenied', 'PreCompact', 'PostCompact',
               'SubagentStart', 'SubagentStop')
# every event but SessionEnd runs in the background, so Claude Code never waits for the office;
# SessionEnd stays in step, as Claude Code may be closing and would not wait for a background hook
IN_STEP = ('SessionEnd',)
MARKER = os.path.join(os.path.expanduser('~'), '.claude', 'office-hooks', '.installed')
STATUS_SCRIPT = os.path.join(HERE, 'office-statusline.py')
STATUS_ORIGINAL = os.path.join(os.path.expanduser('~'), '.claude', 'office-statusline-original.json')


def hook_command():
    py = sys.executable
    if os.name == 'nt':  # pythonw: no console window flashing up
        w = os.path.join(os.path.dirname(py), 'pythonw.exe')
        py = w if os.path.exists(w) else py
    return f'"{py}" "{HOOK_SCRIPT}"'


def status_command():
    py = sys.executable
    if os.name == 'nt':  # the status line prints, so it needs python.exe, not pythonw.exe
        p = os.path.join(os.path.dirname(py), 'python.exe')
        py = p if os.path.exists(p) else py
    return f'"{py}" "{STATUS_SCRIPT}"'


def is_ours(entry):
    return isinstance(entry, dict) and any(
        'office-hook.py' in str(h.get('command', '')) for h in entry.get('hooks', []) if isinstance(h, dict))


def our_hook(event):
    h = {'type': 'command', 'command': hook_command()}
    if event not in IN_STEP:
        h['async'] = True
    return {'hooks': [h]}


def read_settings(add):
    """~/.claude/settings.json as a dict ({} if missing), or None if it is not valid JSON."""
    if not os.path.exists(SETTINGS):
        return {}
    try:
        with open(SETTINGS, encoding='utf-8') as fh:
            settings = json.load(fh)
    except ValueError:
        print('could not read', SETTINGS, '(it is not valid JSON), so it was left unchanged')
        return None
    backup = SETTINGS + '.office-backup'
    if add and not os.path.exists(backup):
        shutil.copy2(SETTINGS, backup)
    return settings if isinstance(settings, dict) else None


def write_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    with open(SETTINGS + '.tmp', 'w', encoding='utf-8') as fh:
        json.dump(settings, fh, indent=2)
    os.replace(SETTINGS + '.tmp', SETTINGS)


def hooks_outdated():
    """True when the hooks were added by an older version and some events are missing."""
    if not os.path.exists(MARKER):
        return False
    try:
        with open(SETTINGS, encoding='utf-8') as fh:
            hooks = json.load(fh).get('hooks') or {}
    except (OSError, ValueError, AttributeError):
        return False
    return any(not any(map(is_ours, hooks.get(ev) or [])) for ev in HOOK_EVENTS)


def set_hooks(add):
    """Adds or removes the office hooks in ~/.claude/settings.json, keeping everything else as it is."""
    settings = read_settings(add)
    if settings is None:
        return
    hooks = settings.setdefault('hooks', {})
    # every event, including ones an older version used, loses its office hook first
    for event in set(HOOK_EVENTS) | {e for e, v in hooks.items() if isinstance(v, list) and any(map(is_ours, v))}:
        kept = [e for e in hooks.get(event, []) if not is_ours(e)]
        if add and event in HOOK_EVENTS:
            kept.append(our_hook(event))
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    if not hooks:
        settings.pop('hooks', None)
    write_settings(settings)
    if add:
        os.makedirs(os.path.dirname(MARKER), exist_ok=True)
        open(MARKER, 'w').close()
        print('added the office hooks to', SETTINGS)
    else:
        if os.path.exists(MARKER):
            os.remove(MARKER)
        print('removed the office hooks from', SETTINGS)


def set_statusline(add):
    """Puts the office status line in front of yours (yours is saved and still shown), or puts yours back."""
    settings = read_settings(add)
    if settings is None:
        return
    current = settings.get('statusLine')
    ours = isinstance(current, dict) and 'office-statusline.py' in str(current.get('command', ''))
    os.makedirs(os.path.dirname(STATUS_ORIGINAL), exist_ok=True)
    if add:
        if not ours:  # keep yours, so the office can run it and put it back later
            with open(STATUS_ORIGINAL, 'w', encoding='utf-8') as fh:
                json.dump({'statusLine': current}, fh, indent=2)
        line = {'type': 'command', 'command': status_command()}
        if isinstance(current, dict):  # your padding and refresh timer still apply
            line.update({k: v for k, v in current.items() if k not in ('type', 'command')})
        settings['statusLine'] = line
        write_settings(settings)
        print('the office now reads the status line in', SETTINGS)
        return
    if ours:
        try:
            with open(STATUS_ORIGINAL, encoding='utf-8') as fh:
                saved = json.load(fh).get('statusLine')
        except (OSError, ValueError, AttributeError):
            saved = None
        if saved:
            settings['statusLine'] = saved
        else:
            settings.pop('statusLine', None)
        write_settings(settings)
    if os.path.exists(STATUS_ORIGINAL):
        os.remove(STATUS_ORIGINAL)
    print('put your own status line back in', SETTINGS)


def main():
    if '--hooks' in sys.argv or '--uninstall-hooks' in sys.argv:
        set_hooks('--hooks' in sys.argv)
        return
    if '--statusline' in sys.argv or '--uninstall-statusline' in sys.argv:
        set_statusline('--statusline' in sys.argv)
        return
    remove = '--uninstall' in sys.argv
    folder = desktop()
    os.makedirs(folder, exist_ok=True)
    if os.name == 'nt':
        windows(folder, remove)
    elif sys.platform == 'darwin':
        mac(folder, remove)
    else:
        linux(folder, remove)
    if remove:  # the small browser profile the full screen shortcut uses, if it was ever made
        shutil.rmtree(os.path.join(os.path.expanduser('~'), '.claude', 'office-browser'), ignore_errors=True)
    print('removed the shortcuts' if remove else 'done: double-click "Claude Office" on the desktop')


if __name__ == '__main__':
    main()
