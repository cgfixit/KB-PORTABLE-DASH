from pathlib import Path

from kbgui.config import load_config
from kbgui.launchers import run_launcher
from kbgui.store import AdminRow, KbRow, delete_secret, initialize, set_secret

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
