from pathlib import Path

from kbgui.config import LAUNCHER_KINDS, load_config

REPO = Path(__file__).resolve().parent.parent


def test_example_config_launchers(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    example = REPO / "config.example.toml"
    (app_dir / "config.example.toml").write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    cfg = load_config(app_dir=app_dir, environ={})
    assert len(cfg.launchers) == 14
    assert {item.kind for item in cfg.launchers} <= set(LAUNCHER_KINDS)
    assert all(item.target == "" for item in cfg.launchers)
    labels = {item.label for item in cfg.launchers}
    assert "Email Hosting" in labels
    assert "IT Glue" in labels
    assert "Webmail" in labels
