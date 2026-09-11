from pathlib import Path
from unittest.mock import patch

from kbgui.config import load_config, write_data_dir_override
from kbgui.launchers import run_launcher
from kbgui.store import AdminRow, BoardRow, KbRow, delete_secret, initialize, set_secret

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = REPO / "examples"


def test_import_crud_search_export(tmp_path: Path) -> None:
    store = initialize(tmp_path, EXAMPLES)
    try:
        seeded = store.list_kb()
        assert seeded, "example KB CSV must import at least one row"
        imported = seeded[0]
        token = next(part for part in imported.issue.replace("/", " ").split() if len(part) > 3)

        found = store.search_kb(token)
        assert any(row.id == imported.id for row in found)

        new_id = store.upsert_kb(
            KbRow(
                id=None,
                customer="Acme",
                ticket="T-9",
                issue="vpn down after sleep",
                resolution="reboot concentrator",
                notes="first pass",
            )
        )
        got = store.get_kb(new_id)
        assert got is not None
        assert got.ticket == "T-9"
        assert got.issue == "vpn down after sleep"

        store.upsert_kb(
            KbRow(
                id=new_id,
                customer=got.customer,
                ticket=got.ticket,
                issue=got.issue,
                resolution="reset tunnel on concentrator",
                notes=got.notes,
            )
        )
        updated = store.get_kb(new_id)
        assert updated is not None
        assert updated.resolution == "reset tunnel on concentrator"

        searched = store.search_kb("tunnel")
        assert any(row.id == new_id for row in searched)

        store.delete_kb(new_id)
        assert store.get_kb(new_id) is None

        export_path = tmp_path / "exported_kb.csv"
        store.export_csv("kb", export_path)
        text = export_path.read_text(encoding="utf-8")
        assert "customer" in text.splitlines()[0]
        assert imported.ticket in text or imported.issue.split()[0] in text

        before = len(store.list_kb())
        store.import_csv("kb", export_path)
        assert len(store.list_kb()) >= before
    finally:
        store.close()


def test_password_never_written_to_sqlite(tmp_path: Path) -> None:
    store = initialize(tmp_path, EXAMPLES)
    try:
        row_id = store.upsert_admin(
            AdminRow(
                id=None,
                kind="firewall",
                fields={"customer": "Ex", "url": "https://x.invalid", "username": "adm"},
            )
        )
        secret = f"probe-{tmp_path.name}-token"
        try:
            result = set_secret("firewall", row_id, secret)
            db_bytes = store.db_path.read_bytes()
            assert secret.encode() not in db_bytes
            csv_path = store.csv_path("firewall")
            csv_bytes = csv_path.read_bytes() if csv_path.exists() else b""
            assert secret.encode() not in csv_bytes
            if not result.stored:
                assert result.refused
                assert "not saved" in result.message.lower()
        finally:
            delete_secret("firewall", row_id)
    finally:
        store.close()


def test_data_dir_env_override(tmp_path: Path) -> None:
    cfg = load_config(app_dir=REPO, environ={"KB_GUI_DATA_DIR": str(tmp_path)})
    assert cfg.data_dir == tmp_path.resolve()


def test_empty_launcher_target_does_not_open() -> None:
    result = run_launcher("url", "")
    assert result.empty_target
    assert result.ok is False
    assert "config" in result.message.lower()


def test_missing_file_launcher_does_not_quit(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-file.txt"
    result = run_launcher("file", str(missing))
    assert result.ok is False
    assert result.empty_target is False
    assert "exist" in result.message.lower()


def test_data_dir_config_roundtrip(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    data_dir = tmp_path / "kb-data"
    app_dir.mkdir()
    data_dir.mkdir()
    write_data_dir_override(app_dir, data_dir)
    cfg = load_config(app_dir=app_dir, environ={})
    assert cfg.data_dir == data_dir.resolve()
    text = (app_dir / "config.toml").read_text(encoding="utf-8")
    assignment = next(ln for ln in text.splitlines() if ln.startswith("data_dir"))
    assert "\\" not in assignment
    store = initialize(cfg.data_dir, EXAMPLES)
    try:
        assert store.db_path.parent == cfg.data_dir / "data"
        assert store.list_kb()
    finally:
        store.close()


def test_board_crud_and_search(tmp_path: Path) -> None:
    store = initialize(tmp_path, EXAMPLES)
    try:
        row_id = store.upsert_board(
            BoardRow(id=None, issue="spooler down", fix="restart spooler", project="print queue")
        )
        hits = store.list_board("spooler")
        assert any(row.id == row_id for row in hits)
        store.upsert_board(
            BoardRow(id=row_id, issue="spooler down", fix="clear stuck job", project="print queue")
        )
        updated = next(row for row in store.list_board() if row.id == row_id)
        assert updated.fix == "clear stuck job"
        store.delete_board(row_id)
        assert all(row.id != row_id for row in store.list_board())
    finally:
        store.close()


def test_admin_export_has_no_password_column(tmp_path: Path) -> None:
    store = initialize(tmp_path, EXAMPLES)
    try:
        for kind in ("firewall", "o365", "credentials"):
            out = tmp_path / f"{kind}.csv"
            store.export_csv(kind, out)
            header = out.read_text(encoding="utf-8").splitlines()[0].lower()
            assert "password" not in header
    finally:
        store.close()


def test_import_old_kb_headers(tmp_path: Path) -> None:
    store = initialize(tmp_path, EXAMPLES)
    try:
        path = tmp_path / "legacy.csv"
        path.write_text(
            "Customer:,Ticket#,Issue,Resolution,Notes\n"
            "OldCo,42,cannot login,reset locally,from old export\n",
            encoding="utf-8",
        )
        store.import_csv("kb", path)
        found = store.search_kb("cannot")
        assert any(row.customer == "OldCo" and row.ticket == "42" for row in found)
    finally:
        store.close()


def test_import_drops_password_column(tmp_path: Path) -> None:
    store = initialize(tmp_path, EXAMPLES)
    try:
        path = tmp_path / "fw.csv"
        token = f"probe-{tmp_path.name}-pw"
        path.write_text(
            "customer,url,username,password\n"
            f"Acme,https://fw.example.invalid,adm,{token}\n",
            encoding="utf-8",
        )
        store.import_csv("firewall", path)
        rows = store.list_admin("firewall")
        assert any(row.fields.get("customer") == "Acme" for row in rows)
        assert token.encode() not in store.db_path.read_bytes()
        exported = tmp_path / "fw-out.csv"
        store.export_csv("firewall", exported)
        text = exported.read_text(encoding="utf-8")
        assert "password" not in text.splitlines()[0].lower()
        assert token not in text
    finally:
        store.close()


def test_first_run_seed_is_idempotent(tmp_path: Path) -> None:
    store = initialize(tmp_path, EXAMPLES)
    first = len(store.list_kb())
    store.close()
    again = initialize(tmp_path, EXAMPLES)
    try:
        assert len(again.list_kb()) == first
    finally:
        again.close()


def test_env_wins_over_toml_data_dir(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    toml_dir = tmp_path / "from-toml"
    env_dir = tmp_path / "from-env"
    app_dir.mkdir()
    toml_dir.mkdir()
    env_dir.mkdir()
    write_data_dir_override(app_dir, toml_dir)
    cfg = load_config(app_dir=app_dir, environ={"KB_GUI_DATA_DIR": str(env_dir)})
    assert cfg.data_dir == env_dir.resolve()


def test_missing_folder_launcher_does_not_quit(tmp_path: Path) -> None:
    result = run_launcher("folder", str(tmp_path / "no-such-dir"))
    assert result.ok is False
    assert result.empty_target is False


def test_empty_command_launcher_asks_for_config() -> None:
    result = run_launcher("command", "   ")
    assert result.empty_target
    assert result.ok is False
    assert "config" in result.message.lower()


def test_command_launcher_uses_shell_false() -> None:
    with patch("kbgui.launchers.subprocess.Popen") as popen:
        result = run_launcher("command", "echo hello")
        assert result.ok is True
        assert result.empty_target is False
        popen.assert_called_once()
        args, kwargs = popen.call_args
        assert kwargs.get("shell") is False
        assert args[0] == ["echo", "hello"]


def test_unknown_launcher_kind_does_not_quit() -> None:
    result = run_launcher("nope", "https://example.invalid")
    assert result.ok is False
    assert "unknown" in result.message.lower()


def test_search_kb_customer_ticket_and_literal_percent(tmp_path: Path) -> None:
    store = initialize(tmp_path, EXAMPLES)
    try:
        new_id = store.upsert_kb(
            KbRow(
                id=None,
                customer="AcmeSearch",
                ticket="T-9",
                issue="vpn down after sleep",
                resolution="reboot concentrator",
                notes="",
            )
        )
        assert any(row.id == new_id for row in store.search_kb("T-9"))
        assert any(row.id == new_id for row in store.search_kb("AcmeSearch"))
        pct_id = store.upsert_kb(
            KbRow(
                id=None,
                customer="PctCo",
                ticket="1",
                issue="disk 100% full",
                resolution="clean",
                notes="",
            )
        )
        hits = store.search_kb("100%")
        assert any(row.id == pct_id for row in hits)
        only_pct = store.search_kb("%")
        assert any(row.id == pct_id for row in only_pct)
        assert len(only_pct) < len(store.list_kb())
    finally:
        store.close()

