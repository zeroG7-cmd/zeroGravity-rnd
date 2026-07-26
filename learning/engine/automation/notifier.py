"""Best-effort desktop notifications for the learning watcher.

Every notification is logged to notifications.log first, so nothing is
ever silently lost even if no popup backend is available on this
machine. Popup order:

1. plyer (optional; ``pip install plyer`` for real cross-platform toasts)
2. a native OS call (PowerShell balloon tip on Windows, osascript on
   macOS, notify-send on Linux)
3. console print only (always happens, as a final fallback)
"""
from __future__ import annotations

import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent / "notifications.log"


def _escape(text: str) -> str:
    """Keep quotes from breaking the PowerShell/osascript one-liners below."""
    return text.replace('"', "'")


def _log(title: str, message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"{timestamp}  {title} - {message}\n")


def _try_plyer(title: str, message: str) -> bool:
    try:
        from plyer import notification as plyer_notification
    except Exception:
        return False
    try:
        plyer_notification.notify(title=title, message=message, timeout=6)
        return True
    except Exception:
        return False


def _try_native(title: str, message: str) -> bool:
    system = platform.system()
    title = _escape(title)
    message = _escape(message)
    try:
        if system == "Windows":
            script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$notify = New-Object System.Windows.Forms.NotifyIcon; "
                "$notify.Icon = [System.Drawing.SystemIcons]::Information; "
                "$notify.Visible = $true; "
                f"$notify.ShowBalloonTip(6000, \"{title}\", \"{message}\", "
                "[System.Windows.Forms.ToolTipIcon]::Info)"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        if system == "Darwin":
            script = f'display notification "{message}" with title "{title}"'
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, timeout=10
            )
            return result.returncode == 0
        if system == "Linux":
            result = subprocess.run(
                ["notify-send", title, message], capture_output=True, timeout=10
            )
            return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
    return False


def notify(title: str, message: str) -> None:
    """Show a notification. Always logs and prints; popup is best-effort."""
    _log(title, message)
    print(f"\n[notification] {title}\n  {message}\n")

    if _try_plyer(title, message):
        return
    _try_native(title, message)
