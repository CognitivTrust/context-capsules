"""Best-effort native clipboard helpers."""

from __future__ import annotations

import platform
import shutil
import subprocess


def copy_to_clipboard(text: str) -> bool:
    argv = _clipboard_copy_argv()
    if argv is None:
        return False
    try:
        completed = subprocess.run(
            argv,
            input=text,
            text=True,
            encoding="utf-8",
            errors="strict",
            shell=False,
            check=False,
            capture_output=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def read_from_clipboard() -> str | None:
    argv = _clipboard_paste_argv()
    if argv is None:
        return None
    try:
        completed = subprocess.run(
            argv,
            text=True,
            encoding="utf-8",
            errors="strict",
            shell=False,
            check=False,
            capture_output=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _clipboard_copy_argv() -> list[str] | None:
    system = platform.system()
    if system == "Windows":
        if shutil.which("clip") is not None:
            return ["clip"]
        return None
    if system == "Darwin":
        if shutil.which("pbcopy") is not None:
            return ["pbcopy"]
        return None
    if shutil.which("wl-copy") is not None:
        return ["wl-copy"]
    if shutil.which("xclip") is not None:
        return ["xclip", "-selection", "clipboard"]
    if shutil.which("xsel") is not None:
        return ["xsel", "--clipboard", "--input"]
    return None


def _clipboard_paste_argv() -> list[str] | None:
    system = platform.system()
    if system == "Windows":
        for command in ("powershell", "pwsh"):
            if shutil.which(command) is not None:
                return [command, "-NoProfile", "-Command", "Get-Clipboard"]
        return None
    if system == "Darwin":
        if shutil.which("pbpaste") is not None:
            return ["pbpaste"]
        return None
    if shutil.which("wl-paste") is not None:
        return ["wl-paste", "--no-newline"]
    if shutil.which("xclip") is not None:
        return ["xclip", "-selection", "clipboard", "-o"]
    if shutil.which("xsel") is not None:
        return ["xsel", "--clipboard", "--output"]
    return None
