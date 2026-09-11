import sys
from pathlib import Path

from kbgui.config import LAUNCHER_KINDS, default_app_dir, examples_dir, load_config

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


def test_frozen_macos_app_dir_is_next_to_bundle(monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "KB-Portable-DASH.app" / "Contents" / "MacOS" / "KB-Portable-DASH"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert default_app_dir() == tmp_path


def test_examples_and_config_fall_back_to_meipass(monkeypatch, tmp_path: Path) -> None:
    bundled = tmp_path / "_bundle"
    examples = bundled / "examples"
    examples.mkdir(parents=True)
    (examples / "kb.example.csv").write_text("customer,ticket,issue,resolution,notes\n", encoding="utf-8")
    (bundled / "config.example.toml").write_text(
        (REPO / "config.example.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "_MEIPASS", str(bundled), raising=False)
    empty_app = tmp_path / "empty"
    empty_app.mkdir()
    assert examples_dir(empty_app) == examples
    cfg = load_config(app_dir=empty_app, environ={})
    assert len(cfg.launchers) == 14
