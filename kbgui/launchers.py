"""Launcher catalog execution. UI class lives here; run_launcher has no Tk."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from kbgui.config import LAUNCHER_KINDS, AppConfig, Launcher


@dataclass(frozen=True)
class LaunchResult:
    ok: bool
    empty_target: bool
    message: str


def run_launcher(kind: str, target: str) -> LaunchResult:
    kind = (kind or "").strip().lower()
    target = (target or "").strip()
    if not target:
        return LaunchResult(False, True, "set this in config")
    if kind not in LAUNCHER_KINDS:
        return LaunchResult(False, False, f"unknown launcher kind: {kind}")
    if kind == "url":
        webbrowser.open(target)
        return LaunchResult(True, False, "")
    if kind in {"folder", "file"}:
        path = Path(target).expanduser()
        if not path.exists():
            return LaunchResult(False, False, "path does not exist")
        return open_path(path)
    args = shlex.split(target, posix=os.name != "nt")
    if not args:
        return LaunchResult(False, True, "set this in config")
    try:
        subprocess.Popen(args, shell=False, close_fds=os.name != "nt")
    except OSError:
        return LaunchResult(False, False, "command failed to start")
    return LaunchResult(True, False, "")


def open_path(path: Path) -> LaunchResult:
    path = Path(path)
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", str(path)], close_fds=True)
    except OSError:
        return LaunchResult(False, False, "could not open path")
    return LaunchResult(True, False, "")


class LaunchersTab:
    """Filled in by app.py after CustomTkinter is imported."""

    def __init__(self, parent, cfg: AppConfig, on_empty, on_error):
        import customtkinter as ctk

        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._cfg = cfg
        self._on_empty = on_empty
        self._on_error = on_error
        hint = ctk.CTkLabel(
            self.frame,
            text="Targets come from config.toml. Empty target does not quit.",
            anchor="w",
        )
        hint.pack(fill="x", padx=8, pady=(8, 12))
        self._ctk = ctk
        self._grid = ctk.CTkScrollableFrame(self.frame)
        self._grid.pack(fill="both", expand=True, padx=8, pady=8)
        self._render(cfg.launchers)

    def _render(self, launchers: list[Launcher]) -> None:
        for child in self._grid.winfo_children():
            child.destroy()
        items = launchers or [Launcher(label="(no launchers in config)", kind="url", target="")]
        for index, item in enumerate(items):
            btn = self._ctk.CTkButton(
                self._grid,
                text=item.label,
                width=220,
                command=lambda it=item: self._click(it),
            )
            btn.grid(row=index // 4, column=index % 4, padx=6, pady=6, sticky="ew")

    def _click(self, item: Launcher) -> None:
        result = run_launcher(item.kind, item.target)
        if result.empty_target:
            self._on_empty(item.label)
            return
        if not result.ok and result.message:
            self._on_error(result.message)

    def reload(self, cfg: AppConfig) -> None:
        self._cfg = cfg
        self._render(cfg.launchers)
