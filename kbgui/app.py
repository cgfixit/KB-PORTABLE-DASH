"""CustomTkinter main window: four tabs + footer."""

from __future__ import annotations

import tkinter.messagebox as messagebox
from pathlib import Path
from tkinter import TclError, filedialog, ttk

import customtkinter as ctk

from kbgui.board import BoardTab
from kbgui.config import (
    AppConfig,
    default_app_dir,
    examples_dir,
    load_config,
    write_data_dir_override,
)
from kbgui.kb import AdminRefsTab, KnowledgeBaseTab
from kbgui.launchers import LaunchersTab
from kbgui.store import Store, initialize


def make_treeview(parent, columns: tuple[tuple[str, str, int], ...]) -> ttk.Treeview:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True, padx=8, pady=4)
    ids = [c[0] for c in columns]
    tree = ttk.Treeview(holder, columns=ids, show="headings", selectmode="browse", style="KB.Treeview")
    scroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    for key, heading, width in columns:
        tree.heading(key, text=heading)
        tree.column(key, width=width, stretch=True)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    tree._holder = holder  # type: ignore[attr-defined]
    return tree


def style_treeview(root: ctk.CTk, appearance: str) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except TclError:
        pass
    dark = appearance.lower() != "light"
    bg = "#2b2b2b" if dark else "#f9f9fa"
    fg = "#dce4ee" if dark else "#1a1a1a"
    sel = "#1f6aa5" if dark else "#3b8ed0"
    heading_bg = "#1f1f1f" if dark else "#e5e5e5"
    style.configure(
        "KB.Treeview",
        background=bg,
        fieldbackground=bg,
        foreground=fg,
        rowheight=26,
        borderwidth=0,
    )
    style.configure("KB.Treeview.Heading", background=heading_bg, foreground=fg, relief="flat")
    style.map("KB.Treeview", background=[("selected", sel)], foreground=[("selected", "#ffffff")])


class App(ctk.CTk):
    def __init__(self, cfg: AppConfig, store: Store):
        super().__init__()
        self.cfg = cfg
        self.store = store
        self.title("KB-Portable-DASH")
        self.geometry(self._initial_geometry())
        self.minsize(800, 560)
        appearance = cfg.appearance
        if appearance == "system":
            appearance = (ctk.get_appearance_mode() or "Dark").lower()
        ctk.set_appearance_mode(cfg.appearance)
        ctk.set_default_color_theme("blue")
        style_treeview(self, appearance)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 0))
        ctk.CTkLabel(header, text="KB-Portable-DASH", font=ctk.CTkFont(size=18, weight="bold")).pack(
            side="left"
        )
        self.theme = ctk.CTkSegmentedButton(header, values=["dark", "light"], command=self._set_theme)
        self.theme.set("light" if appearance == "light" else "dark")
        self.theme.pack(side="right")

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=8)
        self.board = BoardTab(self.tabs.add("Board"), store, make_treeview, self._on_saved)
        self.board.frame.pack(fill="both", expand=True)
        self.kb = KnowledgeBaseTab(
            self.tabs.add("Knowledge Base"), store, make_treeview, self._on_saved, self._copy
        )
        self.kb.frame.pack(fill="both", expand=True)
        self.launchers = LaunchersTab(
            self.tabs.add("Launchers"), cfg, self._empty_launcher, self._info
        )
        self.launchers.frame.pack(fill="both", expand=True)
        self.admin = AdminRefsTab(
            self.tabs.add("Admin refs"), store, make_treeview, self._on_saved, self._info
        )
        self.admin.frame.pack(fill="both", expand=True)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(footer, text="Edit data folder", width=150, command=self.edit_data_folder).pack(
            side="left", padx=4
        )
        ctk.CTkButton(footer, text="Reload", width=90, command=self.reload).pack(side="left", padx=4)
        ctk.CTkButton(footer, text="Quit", width=90, command=self.quit_app).pack(side="right", padx=4)
        self.footer_stamp = ctk.CTkLabel(footer, text="")
        self.footer_stamp.pack(side="right", padx=12)
        self._on_saved(store.last_saved())
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    def _initial_geometry(self) -> str:
        saved = self.store.get_setting("geometry", "")
        return saved or f"{self.cfg.width}x{self.cfg.height}"

    def _set_theme(self, value: str) -> None:
        ctk.set_appearance_mode(value)
        style_treeview(self, value)

    def _on_saved(self, stamp: str) -> None:
        text = f"Last saved: {stamp}" if stamp else "Last saved: never"
        self.footer_stamp.configure(text=text)
        if hasattr(self, "board"):
            self.board.stamp.configure(text=text)

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self._info("Resolution copied to clipboard.")

    def _empty_launcher(self, label: str) -> None:
        messagebox.showinfo("Launcher", f"{label}: set this in config")

    def _info(self, message: str) -> None:
        messagebox.showinfo("KB-Portable-DASH", message)

    def edit_data_folder(self) -> None:
        chosen = filedialog.askdirectory(initialdir=str(self.cfg.data_dir), mustexist=True)
        if not chosen:
            return
        write_data_dir_override(self.cfg.app_dir, Path(chosen))
        self.reload()

    def reload(self) -> None:
        self.store.close()
        self.cfg = load_config(self.cfg.app_dir)
        self.store = initialize(self.cfg.data_dir, examples_dir(self.cfg.app_dir))
        self.board.store = self.store
        self.kb.store = self.store
        self.admin.store = self.store
        self.board.refresh()
        self.kb.refresh()
        self.admin.refresh()
        self.launchers.reload(self.cfg)
        self._on_saved(self.store.last_saved())

    def quit_app(self) -> None:
        try:
            self.store.set_setting("geometry", self.geometry())
        except Exception:
            pass
        try:
            self.store.close()
        except Exception:
            pass
        self.destroy()


def run() -> None:
    cfg = load_config(default_app_dir())
    store = initialize(cfg.data_dir, examples_dir(cfg.app_dir))
    app = App(cfg, store)
    app.mainloop()
