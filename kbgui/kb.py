"""Knowledge Base tab and Admin refs tab."""

from __future__ import annotations

import customtkinter as ctk

from kbgui.launchers import open_path
from kbgui.store import AdminRow, KbRow, Store, has_secret, set_secret


def _destroy_tree(tree) -> None:
    holder = getattr(tree, "_holder", None)
    tree.destroy()
    if holder is not None:
        holder.destroy()

ADMIN_COLUMNS = {
    "firewall": (
        ("customer", "Customer", 200),
        ("url", "Firewall URL", 320),
        ("username", "Username", 160),
    ),
    "o365": (("customer", "Customer", 220), ("username", "Username", 280)),
    "credentials": (("label", "Label", 220), ("username", "Username", 280)),
}


class KnowledgeBaseTab:
    COLUMNS = (
        ("customer", "Customer", 140),
        ("ticket", "Ticket#", 90),
        ("issue", "Issue", 220),
        ("resolution", "Resolution", 260),
        ("notes", "Notes", 180),
    )

    def __init__(self, parent, store: Store, make_treeview, on_saved, copy_text):
        self.store = store
        self._on_saved = on_saved
        self._copy_text = copy_text
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._selected_id: int | None = None

        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(top, text="Search issue / resolution / notes").pack(side="left", padx=(0, 6))
        self.search = ctk.CTkEntry(top, width=360)
        self.search.pack(side="left", fill="x", expand=True)
        self.search.bind("<KeyRelease>", lambda _e: self.refresh())

        self.tree = make_treeview(self.frame, self.COLUMNS)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        editor = ctk.CTkFrame(self.frame, fg_color="transparent")
        editor.pack(fill="x", padx=8, pady=4)
        self.customer = ctk.CTkEntry(editor, placeholder_text="Customer", width=140)
        self.ticket = ctk.CTkEntry(editor, placeholder_text="Ticket#", width=90)
        self.issue = ctk.CTkEntry(editor, placeholder_text="Issue")
        self.resolution = ctk.CTkEntry(editor, placeholder_text="Resolution")
        self.notes = ctk.CTkEntry(editor, placeholder_text="Notes")
        for widget in (self.customer, self.ticket, self.issue, self.resolution, self.notes):
            widget.pack(side="left", fill="x", expand=True, padx=2)
            widget.bind("<Return>", lambda _e: self.save())

        buttons = ctk.CTkFrame(self.frame, fg_color="transparent")
        buttons.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(buttons, text="Add ticket", width=110, command=self.add).pack(side="left", padx=2)
        ctk.CTkButton(buttons, text="Save", width=90, command=self.save).pack(side="left", padx=2)
        ctk.CTkButton(buttons, text="Delete", width=90, command=self.delete).pack(side="left", padx=2)
        ctk.CTkButton(
            buttons, text="Copy resolution", width=140, command=self.copy_resolution
        ).pack(side="left", padx=8)

        self.refresh()

    def refresh(self) -> None:
        query = self.search.get()
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.store.list_kb(query):
            self.tree.insert(
                "",
                "end",
                iid=str(row.id),
                values=(row.customer, row.ticket, row.issue, row.resolution, row.notes),
            )

    def _on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        self._selected_id = int(sel[0])
        vals = self.tree.item(sel[0], "values")
        self._set_editor(*vals)

    def _set_editor(self, customer, ticket, issue, resolution, notes) -> None:
        pairs = (
            (self.customer, customer),
            (self.ticket, ticket),
            (self.issue, issue),
            (self.resolution, resolution),
            (self.notes, notes),
        )
        for widget, value in pairs:
            widget.delete(0, "end")
            widget.insert(0, value)

    def _read_editor(self) -> KbRow:
        return KbRow(
            id=self._selected_id,
            customer=self.customer.get().strip(),
            ticket=self.ticket.get().strip(),
            issue=self.issue.get().strip(),
            resolution=self.resolution.get().strip(),
            notes=self.notes.get().strip(),
        )

    def add(self) -> None:
        self._selected_id = None
        self.tree.selection_remove(self.tree.selection())
        self._set_editor("", "", "", "", "")
        self.customer.focus_set()

    def save(self) -> None:
        row = self._read_editor()
        if not any((row.customer, row.ticket, row.issue, row.resolution, row.notes)):
            return
        new_id = self.store.upsert_kb(row)
        self._selected_id = new_id
        self.refresh()
        if str(new_id) in self.tree.get_children():
            self.tree.selection_set(str(new_id))
        self._on_saved(self.store.last_saved())

    def delete(self) -> None:
        if self._selected_id is None:
            return
        self.store.delete_kb(self._selected_id)
        self._selected_id = None
        self._set_editor("", "", "", "", "")
        self.refresh()
        self._on_saved(self.store.last_saved())

    def copy_resolution(self) -> None:
        text = self.resolution.get()
        if not text and self._selected_id is not None:
            row = self.store.get_kb(self._selected_id)
            text = row.resolution if row else ""
        if text:
            self._copy_text(text)


class AdminRefsTab:
    def __init__(self, parent, store: Store, make_treeview, on_saved, on_message):
        self.store = store
        self._on_saved = on_saved
        self._on_message = on_message
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.kind = "firewall"
        self._selected_id: int | None = None
        self._make_treeview = make_treeview

        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))
        self.kind_switch = ctk.CTkSegmentedButton(
            top,
            values=["Firewall", "O365", "Creds"],
            command=self._switch,
        )
        self.kind_switch.set("Firewall")
        self.kind_switch.pack(side="left")
        ctk.CTkButton(
            top, text="Open in Excel/default app", width=200, command=self.open_in_os
        ).pack(side="right", padx=4)

        self.tree_host = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.tree_host.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree = make_treeview(self.tree_host, ADMIN_COLUMNS[self.kind])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        editor = ctk.CTkFrame(self.frame, fg_color="transparent")
        editor.pack(fill="x", padx=8, pady=4)
        self.field_entries: dict[str, ctk.CTkEntry] = {}
        self.fields_row = ctk.CTkFrame(editor, fg_color="transparent")
        self.fields_row.pack(fill="x")
        self._rebuild_fields()

        secret_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        secret_row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(secret_row, text="Password (optional, masked)").pack(side="left", padx=(0, 6))
        self.password = ctk.CTkEntry(secret_row, show="*", width=220)
        self.password.pack(side="left", padx=4)
        self.secret_status = ctk.CTkLabel(secret_row, text="")
        self.secret_status.pack(side="left", padx=8)
        ctk.CTkButton(secret_row, text="Store password", width=140, command=self.store_password).pack(
            side="left", padx=4
        )

        buttons = ctk.CTkFrame(self.frame, fg_color="transparent")
        buttons.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(buttons, text="Add", width=90, command=self.add).pack(side="left", padx=2)
        ctk.CTkButton(buttons, text="Save", width=90, command=self.save).pack(side="left", padx=2)
        ctk.CTkButton(buttons, text="Delete", width=90, command=self.delete).pack(side="left", padx=2)

        self.refresh()

    def _switch(self, label: str) -> None:
        mapping = {"Firewall": "firewall", "O365": "o365", "Creds": "credentials"}
        self.kind = mapping.get(label, "firewall")
        self._selected_id = None
        _destroy_tree(self.tree)
        self.tree = self._make_treeview(self.tree_host, ADMIN_COLUMNS[self.kind])
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._rebuild_fields()
        self.password.delete(0, "end")
        self.refresh()

    def _rebuild_fields(self) -> None:
        for child in self.fields_row.winfo_children():
            child.destroy()
        self.field_entries = {}
        for key, heading, _width in ADMIN_COLUMNS[self.kind]:
            entry = ctk.CTkEntry(self.fields_row, placeholder_text=heading)
            entry.pack(side="left", fill="x", expand=True, padx=2)
            self.field_entries[key] = entry

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        cols = [c[0] for c in ADMIN_COLUMNS[self.kind]]
        for row in self.store.list_admin(self.kind):
            values = tuple(row.fields.get(c, "") for c in cols)
            self.tree.insert("", "end", iid=str(row.id), values=values)
        self._update_secret_status()

    def _on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        self._selected_id = int(sel[0])
        vals = self.tree.item(sel[0], "values")
        for (_key, entry), value in zip(self.field_entries.items(), vals, strict=False):
            entry.delete(0, "end")
            entry.insert(0, value)
        self.password.delete(0, "end")
        self._update_secret_status()

    def _update_secret_status(self) -> None:
        if self._selected_id is not None and has_secret(self.kind, self._selected_id):
            self.secret_status.configure(text="stored as ••••••••")
        else:
            self.secret_status.configure(text="not stored")

    def add(self) -> None:
        self._selected_id = None
        self.tree.selection_remove(self.tree.selection())
        for entry in self.field_entries.values():
            entry.delete(0, "end")
        self.password.delete(0, "end")
        self._update_secret_status()

    def save(self) -> None:
        fields = {k: e.get().strip() for k, e in self.field_entries.items()}
        if not any(fields.values()):
            return
        row_id = self.store.upsert_admin(AdminRow(id=self._selected_id, kind=self.kind, fields=fields))
        self._selected_id = row_id
        typed = self.password.get()
        if typed:
            result = set_secret(self.kind, row_id, typed)
            self.password.delete(0, "end")
            if result.refused:
                self._on_message(result.message)
            elif result.message:
                self._on_message(result.message)
        self.refresh()
        if str(row_id) in self.tree.get_children():
            self.tree.selection_set(str(row_id))
        self._on_saved(self.store.last_saved())

    def store_password(self) -> None:
        if self._selected_id is None:
            self.save()
            return
        typed = self.password.get()
        if not typed:
            self._on_message("Enter a password to store. It is never written to CSV or sqlite.")
            return
        result = set_secret(self.kind, self._selected_id, typed)
        self.password.delete(0, "end")
        self._update_secret_status()
        self._on_message(result.message)

    def delete(self) -> None:
        if self._selected_id is None:
            return
        self.store.delete_admin(self.kind, self._selected_id)
        self._selected_id = None
        self.add()
        self.refresh()
        self._on_saved(self.store.last_saved())

    def open_in_os(self) -> None:
        path = self.store.csv_path(self.kind)
        self.store.export_csv(self.kind, path)
        result = open_path(path)
        if not result.ok:
            self._on_message(result.message)
