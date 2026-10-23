# Double-click launcher for the Claude office (the desktop shortcuts point here). Windows, macOS, Linux.
# Starts the office server if it is not running yet, then opens the office in its own small
# browser app window (no tabs or address bar): Edge, Chrome, Brave or Chromium, whichever is found.
# Falls back to the default browser.
#   open-office.pyw            start if needed and open the window
#   open-office.pyw --server   only start the server in the background (used by the skill)
#   open-office.pyw --stop     stop the server
import glob
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 7788
URL = f'http://127.0.0.1:{PORT}/?app'  # ?app: the window closes itself when the office is stopped
SIZE = '--window-size=720,620'  # the room on top, the session list below
# "Desktop shortcut opens in full screen" in the settings: a browser that is already running ignores
# start-up flags, so the full-screen window gets its own small browser profile
FULL_PROFILE = os.path.join(os.path.expanduser('~'), '.claude', 'office-browser')


def running():
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(('127.0.0.1', PORT)) == 0


def detached(cmd):
    """Starts cmd with no console window, so it outlives this launcher."""
    if os.name == 'nt':
        flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        subprocess.Popen(cmd, creationflags=flags, close_fds=True)
    else:
        subprocess.Popen(cmd, start_new_session=True, close_fds=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_server():
    if running():
        return
    py = sys.executable
    if os.name == 'nt':  # pythonw has no console window
        w = os.path.join(os.path.dirname(py), 'pythonw.exe')
        py = w if os.path.exists(w) else py
    detached([py, os.path.join(HERE, 'claude-office.py')])
    for _ in range(50):  # wait up to 5 seconds for the server
        if running():
            break
        time.sleep(0.1)


def stop_server():
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/quit', timeout=2)
    except OSError:
        pass


def app_browser():
    """A Chromium browser that can open a page as a plain app window, or None."""
    if sys.platform == 'darwin':
        for a in ('Google Chrome', 'Microsoft Edge', 'Brave Browser', 'Chromium', 'Vivaldi'):
            for root in ('/Applications', os.path.expanduser('~/Applications')):
                exe = os.path.join(root, a + '.app', 'Contents', 'MacOS', a)
                if os.path.exists(exe):
                    return exe
        return None
    if os.name == 'nt':
        found = []
        for v in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA'):
            base = os.environ.get(v, '')
            if base:
                found += [os.path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
                          os.path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe'),
                          os.path.join(base, 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe')]
        return next((e for e in found if os.path.exists(e)), None)
    for name in ('google-chrome', 'google-chrome-stable', 'microsoft-edge', 'brave-browser',
                 'chromium', 'chromium-browser'):
        exe = shutil.which(name)
        if exe:
            return exe
    flatpak = glob.glob('/var/lib/flatpak/exports/bin/*hromium*')
    return flatpak[0] if flatpak else None


def wants_full():
    try:
        sys.path.insert(0, HERE)
        import tracker
        return tracker.settings()['full']
    except Exception:
        return False


def main():
    if '--stop' in sys.argv:
        stop_server()
        return
    start_server()
    if '--server' in sys.argv:
        return
    exe = app_browser()
    if exe and wants_full():
        detached([exe, f'--app={URL}', '--start-fullscreen', f'--user-data-dir={FULL_PROFILE}',
                  '--no-first-run', '--no-default-browser-check'])
    elif exe:
        detached([exe, f'--app={URL}', SIZE])
    else:
        webbrowser.open(URL)


if __name__ == '__main__':
    main()
