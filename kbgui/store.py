"""SQLite persistence, CSV import/export, first-run seed, OS secret store.

No Tk imports. Never writes passwords to sqlite or CSV.
"""

from __future__ import annotations

import csv
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# Keep this id stable so Keychain / Credential Manager entries survive the GitHub rename.
SERVICE = "kb-gui-lite"

BOARD_FIELDS = ("issue", "fix", "project")
KB_FIELDS = ("customer", "ticket", "issue", "resolution", "notes")
FIREWALL_FIELDS = ("customer", "url", "username")
O365_FIELDS = ("customer", "username")
CREDS_FIELDS = ("label", "username")

KIND_FIELDS = {
    "board": BOARD_FIELDS,
    "kb": KB_FIELDS,
    "firewall": FIREWALL_FIELDS,
    "o365": O365_FIELDS,
    "credentials": CREDS_FIELDS,
}

KIND_TABLE = {
    "board": "board",
    "kb": "kb",
    "firewall": "firewall",
    "o365": "o365",
    "credentials": "credentials",
}

KIND_CSV_NAME = {
    "board": "notifications.csv",
    "kb": "kb.csv",
    "firewall": "firewall.csv",
    "o365": "o365.csv",
    "credentials": "credentials.csv",
}

KIND_EXAMPLE = {
    "board": "notifications.example.csv",
    "kb": "kb.example.csv",
    "firewall": "firewall.example.csv",
    "o365": "o365.example.csv",
    "credentials": "credentials.example.csv",
}

HEADER_ALIASES: dict[str, str | None] = {
    "known_issues": "issue",
    "issue": "issue",
    "known_fixes": "fix",
    "fix": "fix",
    "fixes": "fix",
    "ongoing_projects": "project",
    "project": "project",
    "projects": "project",
    "customer": "customer",
    "ticket": "ticket",
    "resolution": "resolution",
    "notes": "notes",
    "firewall_url": "url",
    "url": "url",
    "username": "username",
    "label": "label",
    "password": None,
}


@dataclass
class BoardRow:
    id: int | None
    issue: str
    fix: str
    project: str


@dataclass
class KbRow:
    id: int | None
    customer: str
    ticket: str
    issue: str
    resolution: str
    notes: str


@dataclass
class AdminRow:
    id: int | None
    kind: str
    fields: dict[str, str]


@dataclass
class SecretResult:
    stored: bool
    refused: bool
    message: str


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _norm_header(raw: str) -> str:
    h = raw.strip().strip(":").lower().replace("#", "")
    h = "_".join(h.split())
    return h


def _map_headers(headers: list[str]) -> list[str | None]:
    mapped: list[str | None] = []
    for h in headers:
        key = _norm_header(h)
        mapped.append(HEADER_ALIASES.get(key, key if key else None))
    return mapped


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir).resolve()
        self.files_dir = self.data_dir / "data"
        self.db_path = self.files_dir / "kb.sqlite"
        self._conn: sqlite3.Connection | None = None
        self._fts = False

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("store is closed")
        return self._conn

    def open(self) -> None:
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, timeout=5)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._init_schema()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _init_schema(self) -> None:
        c = self.conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS board (
                id INTEGER PRIMARY KEY,
                issue TEXT NOT NULL DEFAULT '',
                fix TEXT NOT NULL DEFAULT '',
                project TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS kb (
                id INTEGER PRIMARY KEY,
                customer TEXT NOT NULL DEFAULT '',
                ticket TEXT NOT NULL DEFAULT '',
                issue TEXT NOT NULL DEFAULT '',
                resolution TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS firewall (
                id INTEGER PRIMARY KEY,
                customer TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS o365 (
                id INTEGER PRIMARY KEY,
                customer TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY,
                label TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self._fts = self._init_fts()
        c.commit()

    def _init_fts(self) -> bool:
        c = self.conn
        try:
            c.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5("
                "issue, resolution, notes, content='kb', content_rowid='id')"
            )
        except sqlite3.OperationalError:
            return False
        c.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS kb_ai AFTER INSERT ON kb BEGIN
                INSERT INTO kb_fts(rowid, issue, resolution, notes)
                VALUES (new.id, new.issue, new.resolution, new.notes);
            END;
            CREATE TRIGGER IF NOT EXISTS kb_ad AFTER DELETE ON kb BEGIN
                INSERT INTO kb_fts(kb_fts, rowid, issue, resolution, notes)
                VALUES ('delete', old.id, old.issue, old.resolution, old.notes);
            END;
            CREATE TRIGGER IF NOT EXISTS kb_au AFTER UPDATE ON kb BEGIN
                INSERT INTO kb_fts(kb_fts, rowid, issue, resolution, notes)
                VALUES ('delete', old.id, old.issue, old.resolution, old.notes);
                INSERT INTO kb_fts(rowid, issue, resolution, notes)
                VALUES (new.id, new.issue, new.resolution, new.notes);
            END;
            """
        )
        try:
            n_kb = c.execute("SELECT COUNT(*) FROM kb").fetchone()[0]
            n_fts = c.execute("SELECT COUNT(*) FROM kb_fts").fetchone()[0]
            if n_fts == 0 and n_kb:
                c.execute("INSERT INTO kb_fts(kb_fts) VALUES('rebuild')")
        except sqlite3.OperationalError:
            pass
        return True

    def ensure_seeded(self, examples: Path) -> None:
        """Copy example CSVs into the data dir if missing, import if DB is empty."""
        examples = Path(examples)
        for kind, example_name in KIND_EXAMPLE.items():
            dest = self.files_dir / KIND_CSV_NAME[kind]
            src = examples / example_name
            if not dest.exists() and src.is_file():
                dest.write_bytes(src.read_bytes())
        if self._is_empty():
            for kind in KIND_FIELDS:
                path = self.files_dir / KIND_CSV_NAME[kind]
                if path.is_file():
                    self.import_csv(kind, path)

    def _is_empty(self) -> bool:
        for table in KIND_TABLE.values():
            n = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if n:
                return False
        return True

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return default if row is None else row["value"]

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def mark_saved(self) -> str:
        stamp = _utc_now()
        self.set_setting("last_saved", stamp)
        return stamp

    def last_saved(self) -> str:
        return self.get_setting("last_saved", "")

    def list_board(self, query: str = "") -> list[BoardRow]:
        q = query.strip()
        if q:
            like = _like_pattern(q)
            rows = self.conn.execute(
                "SELECT id, issue, fix, project FROM board "
                "WHERE issue LIKE ? ESCAPE '\\' OR fix LIKE ? ESCAPE '\\' "
                "OR project LIKE ? ESCAPE '\\' ORDER BY id",
                (like, like, like),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT id, issue, fix, project FROM board ORDER BY id"
            ).fetchall()
        return [BoardRow(r["id"], r["issue"], r["fix"], r["project"]) for r in rows]

    def upsert_board(self, row: BoardRow) -> int:
        if row.id is None:
            cur = self.conn.execute(
                "INSERT INTO board(issue, fix, project) VALUES(?, ?, ?)",
                (row.issue, row.fix, row.project),
            )
            self.conn.commit()
            self.mark_saved()
            return int(cur.lastrowid)
        self.conn.execute(
            "UPDATE board SET issue = ?, fix = ?, project = ? WHERE id = ?",
            (row.issue, row.fix, row.project, row.id),
        )
        self.conn.commit()
        self.mark_saved()
        return row.id

    def delete_board(self, row_id: int) -> None:
        self.conn.execute("DELETE FROM board WHERE id = ?", (row_id,))
        self.conn.commit()
        self.mark_saved()

    def list_kb(self, query: str = "") -> list[KbRow]:
        q = query.strip()
        if not q:
            rows = self.conn.execute(
                "SELECT id, customer, ticket, issue, resolution, notes FROM kb ORDER BY id"
            ).fetchall()
            return [_kb_from_row(r) for r in rows]
        return self.search_kb(q)

    def get_kb(self, row_id: int) -> KbRow | None:
        r = self.conn.execute(
            "SELECT id, customer, ticket, issue, resolution, notes FROM kb WHERE id = ?",
            (row_id,),
        ).fetchone()
        return None if r is None else _kb_from_row(r)

    def search_kb(self, query: str) -> list[KbRow]:
        q = query.strip()
        if not q:
            return self.list_kb()
        by_id: dict[int, KbRow] = {}
        if self._fts:
            try:
                rows = self.conn.execute(
                    "SELECT kb.id, kb.customer, kb.ticket, kb.issue, kb.resolution, kb.notes "
                    "FROM kb JOIN kb_fts ON kb.id = kb_fts.rowid "
                    "WHERE kb_fts MATCH ? ORDER BY kb.id",
                    (_fts_query(q),),
                ).fetchall()
                for r in rows:
                    by_id[int(r["id"])] = _kb_from_row(r)
            except sqlite3.OperationalError:
                pass
        like = _like_pattern(q)
        rows = self.conn.execute(
            "SELECT id, customer, ticket, issue, resolution, notes FROM kb "
            "WHERE issue LIKE ? ESCAPE '\\' OR resolution LIKE ? ESCAPE '\\' "
            "OR notes LIKE ? ESCAPE '\\' OR customer LIKE ? ESCAPE '\\' "
            "OR ticket LIKE ? ESCAPE '\\' ORDER BY id",
            (like, like, like, like, like),
        ).fetchall()
        for r in rows:
            by_id[int(r["id"])] = _kb_from_row(r)
        return [by_id[i] for i in sorted(by_id)]

    def upsert_kb(self, row: KbRow) -> int:
        if row.id is None:
            cur = self.conn.execute(
                "INSERT INTO kb(customer, ticket, issue, resolution, notes) "
                "VALUES(?, ?, ?, ?, ?)",
                (row.customer, row.ticket, row.issue, row.resolution, row.notes),
            )
            self.conn.commit()
            self.mark_saved()
            return int(cur.lastrowid)
        self.conn.execute(
            "UPDATE kb SET customer = ?, ticket = ?, issue = ?, resolution = ?, notes = ? "
            "WHERE id = ?",
            (row.customer, row.ticket, row.issue, row.resolution, row.notes, row.id),
        )
        self.conn.commit()
        self.mark_saved()
        return row.id

    def delete_kb(self, row_id: int) -> None:
        self.conn.execute("DELETE FROM kb WHERE id = ?", (row_id,))
        self.conn.commit()
        self.mark_saved()

    def list_admin(self, kind: str, query: str = "") -> list[AdminRow]:
        fields = KIND_FIELDS[kind]
        table = KIND_TABLE[kind]
        cols = ", ".join(["id", *fields])
        q = query.strip()
        if q:
            likes = " OR ".join(f"{f} LIKE ? ESCAPE '\\'" for f in fields)
            params = tuple(_like_pattern(q) for _ in fields)
            rows = self.conn.execute(
                f"SELECT {cols} FROM {table} WHERE {likes} ORDER BY id", params
            ).fetchall()
        else:
            rows = self.conn.execute(f"SELECT {cols} FROM {table} ORDER BY id").fetchall()
        out: list[AdminRow] = []
        for r in rows:
            out.append(
                AdminRow(
                    id=r["id"],
                    kind=kind,
                    fields={f: r[f] for f in fields},
                )
            )
        return out

    def upsert_admin(self, row: AdminRow) -> int:
        fields = KIND_FIELDS[row.kind]
        table = KIND_TABLE[row.kind]
        values = [row.fields.get(f, "") for f in fields]
        if row.id is None:
            placeholders = ", ".join("?" for _ in fields)
            cur = self.conn.execute(
                f"INSERT INTO {table}({', '.join(fields)}) VALUES({placeholders})",
                values,
            )
            self.conn.commit()
            self.mark_saved()
            return int(cur.lastrowid)
        assignments = ", ".join(f"{f} = ?" for f in fields)
        self.conn.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?",
            [*values, row.id],
        )
        self.conn.commit()
        self.mark_saved()
        return row.id

    def delete_admin(self, kind: str, row_id: int) -> None:
        table = KIND_TABLE[kind]
        self.conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        self.conn.commit()
        delete_secret(kind, row_id)
        self.mark_saved()

    def import_csv(self, kind: str, path: Path) -> int:
        fields = KIND_FIELDS[kind]
        table = KIND_TABLE[kind]
        path = Path(path)
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            try:
                headers = next(reader)
            except StopIteration:
                return 0
            mapped = _map_headers(headers)
            count = 0
            for raw in reader:
                if not any(cell.strip() for cell in raw):
                    continue
                record = {f: "" for f in fields}
                for i, dest in enumerate(mapped):
                    if dest is None or dest not in record or i >= len(raw):
                        continue
                    record[dest] = raw[i].strip()
                if not any(record.values()):
                    continue
                placeholders = ", ".join("?" for _ in fields)
                self.conn.execute(
                    f"INSERT INTO {table}({', '.join(fields)}) VALUES({placeholders})",
                    [record[f] for f in fields],
                )
                count += 1
        self.conn.commit()
        if count:
            self.mark_saved()
        return count

    def export_csv(self, kind: str, path: Path) -> Path:
        fields = KIND_FIELDS[kind]
        table = KIND_TABLE[kind]
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.conn.execute(
            f"SELECT {', '.join(fields)} FROM {table} ORDER BY id"
        ).fetchall()
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(list(fields))
            for r in rows:
                writer.writerow([r[f] for f in fields])
        return path

    def csv_path(self, kind: str) -> Path:
        return self.files_dir / KIND_CSV_NAME[kind]


def initialize(data_dir: Path, examples: Path | None = None) -> Store:
    store = Store(data_dir)
    store.open()
    if examples is not None:
        store.ensure_seeded(examples)
    return store


def _kb_from_row(r: sqlite3.Row) -> KbRow:
    return KbRow(
        id=r["id"],
        customer=r["customer"],
        ticket=r["ticket"],
        issue=r["issue"],
        resolution=r["resolution"],
        notes=r["notes"],
    )


def _like_pattern(raw: str) -> str:
    escaped = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _fts_query(raw: str) -> str:
    token = "".join(ch if ch.isalnum() else " " for ch in raw).strip()
    if not token:
        return '""'
    parts = [p for p in token.split() if p]
    return " AND ".join(f"{p}*" for p in parts)


def _account(kind: str, row_id: int) -> str:
    return f"{kind}:{row_id}"


def set_secret(kind: str, row_id: int, password: str) -> SecretResult:
    if not password:
        return SecretResult(False, False, "")
    ok, err = _os_set(_account(kind, row_id), password)
    if ok:
        return SecretResult(True, False, "Password stored in the OS credential store.")
    return SecretResult(
        False,
        True,
        "OS credential store unavailable. Password was not saved.",
    )


def has_secret(kind: str, row_id: int) -> bool:
    return _os_has(_account(kind, row_id))


def delete_secret(kind: str, row_id: int) -> None:
    _os_delete(_account(kind, row_id))


def _os_set(account: str, password: str) -> tuple[bool, str]:
    if sys.platform == "darwin":
        return _mac_set(account, password)
    if sys.platform == "win32":
        return _win_set(account, password)
    return False, "unsupported"


def _os_has(account: str) -> bool:
    if sys.platform == "darwin":
        return _mac_has(account)
    if sys.platform == "win32":
        return _win_has(account)
    return False


def _os_delete(account: str) -> None:
    if sys.platform == "darwin":
        _mac_delete(account)
    elif sys.platform == "win32":
        _win_delete(account)


def _mac_set(account: str, password: str) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                SERVICE,
                "-a",
                account,
                "-w",
                password,
            ],
            check=False,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, "unavailable"
    return proc.returncode == 0, ""


def _mac_has(account: str) -> bool:
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", SERVICE, "-a", account],
            check=False,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _mac_delete(account: str) -> None:
    try:
        subprocess.run(
            ["security", "delete-generic-password", "-s", SERVICE, "-a", account],
            check=False,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def _win_api():
    """Windows Credential Manager via ctypes. Prototypes required on 64-bit."""
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.c_void_p),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
    advapi32.CredWriteW.restype = wintypes.BOOL
    advapi32.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    advapi32.CredDeleteW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    return ctypes, CREDENTIAL, advapi32


def _win_set(account: str, password: str) -> tuple[bool, str]:
    try:
        ctypes, credential_cls, advapi32 = _win_api()
    except (ImportError, OSError, AttributeError):
        return False, "unavailable"
    blob = password.encode("utf-16-le")
    buf = ctypes.create_string_buffer(blob, len(blob))
    cred = credential_cls()
    cred.Type = 1  # CRED_TYPE_GENERIC
    cred.TargetName = f"{SERVICE}/{account}"
    cred.CredentialBlobSize = len(blob)
    cred.CredentialBlob = ctypes.cast(buf, ctypes.c_void_p)
    cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE
    cred.UserName = account
    try:
        ok = advapi32.CredWriteW(ctypes.byref(cred), 0)
    except OSError:
        return False, "unavailable"
    return bool(ok), ""


def _win_has(account: str) -> bool:
    try:
        ctypes, _credential_cls, advapi32 = _win_api()
    except (ImportError, OSError, AttributeError):
        return False
    ptr = ctypes.c_void_p()
    try:
        ok = advapi32.CredReadW(f"{SERVICE}/{account}", 1, 0, ctypes.byref(ptr))
    except OSError:
        return False
    if ok and ptr.value:
        advapi32.CredFree(ptr)
        return True
    return False


def _win_delete(account: str) -> None:
    try:
        _ctypes, _credential_cls, advapi32 = _win_api()
    except (ImportError, OSError, AttributeError):
        return
    try:
        advapi32.CredDeleteW(f"{SERVICE}/{account}", 1, 0)
    except OSError:
        return


