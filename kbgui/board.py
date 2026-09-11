"""Board tab: Known Issues / Fixes / Projects."""

from __future__ import annotations

import customtkinter as ctk

from kbgui.store import BoardRow, Store


class BoardTab:
    COLUMNS = (
        ("issue", "Known Issues", 280),
        ("fix", "Known Fixes", 280),
        ("project", "Ongoing Projects", 280),
    )

    def __init__(self, parent, store: Store, make_treeview, on_saved):
        self.store = store
        self._on_saved = on_saved
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._selected_id: int | None = None
        self._saving = False

        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(top, text="Search").pack(side="left", padx=(0, 6))
        self.search = ctk.CTkEntry(top, width=320)
        self.search.pack(side="left", fill="x", expand=True)
        self.search.bind("<KeyRelease>", lambda _e: self.refresh())

        self.tree = make_treeview(self.frame, self.COLUMNS)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        editor = ctk.CTkFrame(self.frame, fg_color="transparent")
        editor.pack(fill="x", padx=8, pady=4)
        self.issue = ctk.CTkEntry(editor, placeholder_text="Known issue")
        self.fix = ctk.CTkEntry(editor, placeholder_text="Known fix")
        self.project = ctk.CTkEntry(editor, placeholder_text="Ongoing project")
        self.issue.pack(side="left", fill="x", expand=True, padx=2)
        self.fix.pack(side="left", fill="x", expand=True, padx=2)
        self.project.pack(side="left", fill="x", expand=True, padx=2)
        for widget in (self.issue, self.fix, self.project):
            widget.bind("<FocusOut>", self._on_blur)
            widget.bind("<Return>", lambda _e: self.save())

        buttons = ctk.CTkFrame(self.frame, fg_color="transparent")
        buttons.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(buttons, text="Add", width=90, command=self.add).pack(side="left", padx=2)
        ctk.CTkButton(buttons, text="Save", width=90, command=self.save).pack(side="left", padx=2)
        ctk.CTkButton(buttons, text="Delete", width=90, command=self.delete).pack(side="left", padx=2)
        self.stamp = ctk.CTkLabel(buttons, text="")
        self.stamp.pack(side="right", padx=4)

        self.refresh()

    def refresh(self) -> None:
        query = self.search.get()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.store.list_board(query):
            self.tree.insert("", "end", iid=str(row.id), values=(row.issue, row.fix, row.project))
        last = self.store.last_saved()
        self.stamp.configure(text=f"Last saved: {last}" if last else "Last saved: never")

    def _on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        row_id = int(sel[0])
        self._selected_id = row_id
        vals = self.tree.item(sel[0], "values")
        self._set_editor(vals[0], vals[1], vals[2])

    def _set_editor(self, issue: str, fix: str, project: str) -> None:
        for widget, value in ((self.issue, issue), (self.fix, fix), (self.project, project)):
            widget.delete(0, "end")
            widget.insert(0, value)

    def _read_editor(self) -> BoardRow:
        return BoardRow(
            id=self._selected_id,
            issue=self.issue.get().strip(),
            fix=self.fix.get().strip(),
            project=self.project.get().strip(),
        )

    def add(self) -> None:
        self._selected_id = None
        self.tree.selection_remove(self.tree.selection())
        self._set_editor("", "", "")
        self.issue.focus_set()

    def save(self) -> None:
        row = self._read_editor()
        if not any((row.issue, row.fix, row.project)):
            return
        self._saving = True
        try:
            new_id = self.store.upsert_board(row)
            self._selected_id = new_id
            self.refresh()
            if str(new_id) in self.tree.get_children():
                self.tree.selection_set(str(new_id))
            self._on_saved(self.store.last_saved())
        finally:
            self._saving = False

    def _on_blur(self, _event=None) -> None:
        if self._saving:
            return
        row = self._read_editor()
        if not any((row.issue, row.fix, row.project)):
            return
        self.save()

    def delete(self) -> None:
        if self._selected_id is None:
            return
        self.store.delete_board(self._selected_id)
        self._selected_id = None
        self._set_editor("", "", "")
        self.refresh()
        self._on_saved(self.store.last_saved())
