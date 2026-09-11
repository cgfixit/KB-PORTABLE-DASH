"""Data-dir resolution and TOML config. No Tk imports."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

LAUNCHER_KINDS = ("url", "folder", "file", "command")
DEFAULT_WIDTH = 1100
DEFAULT_HEIGHT = 750
DEFAULT_APPEARANCE = "dark"


@dataclass(frozen=True)
class Launcher:
    label: str
    kind: str
    target: str


@dataclass
class AppConfig:
    app_dir: Path
    data_dir: Path
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    appearance: str = DEFAULT_APPEARANCE
    launchers: list[Launcher] = field(default_factory=list)
    config_path: Path | None = None


def default_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def examples_dir(app_dir: Path) -> Path:
    candidate = app_dir / "examples"
    if candidate.is_dir():
        return candidate
    return Path(__file__).resolve().parent.parent / "examples"


def _read_toml(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _parse_launchers(raw: object) -> list[Launcher]:
    if not isinstance(raw, list):
        return []
    out: list[Launcher] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        kind = str(item.get("kind", "url")).strip().lower()
        target = str(item.get("target", "")).strip()
        if kind not in LAUNCHER_KINDS:
            kind = "url"
        if not label:
            continue
        out.append(Launcher(label=label, kind=kind, target=target))
    return out


def load_config(
    app_dir: Path | None = None,
    environ: dict[str, str] | None = None,
) -> AppConfig:
    app_dir = (app_dir or default_app_dir()).resolve()
    environ = environ if environ is not None else os.environ

    cfg_path = app_dir / "config.toml"
    example_path = app_dir / "config.example.toml"
    raw: dict = {}
    used_path: Path | None = None
    if cfg_path.is_file():
        raw = _read_toml(cfg_path)
        used_path = cfg_path
    elif example_path.is_file():
        raw = _read_toml(example_path)
        used_path = example_path

    window = raw.get("window") if isinstance(raw.get("window"), dict) else {}
    width = int(window.get("width", DEFAULT_WIDTH) or DEFAULT_WIDTH)
    height = int(window.get("height", DEFAULT_HEIGHT) or DEFAULT_HEIGHT)
    appearance = str(window.get("appearance", DEFAULT_APPEARANCE) or DEFAULT_APPEARANCE).lower()
    if appearance not in {"dark", "light", "system"}:
        appearance = DEFAULT_APPEARANCE

    env_dir = (environ.get("KB_GUI_DATA_DIR") or "").strip()
    toml_dir = str(raw.get("data_dir", "") or "").strip()
    if env_dir:
        data_dir = Path(env_dir).expanduser().resolve()
    elif toml_dir:
        data_dir = Path(toml_dir).expanduser().resolve()
    else:
        data_dir = app_dir

    return AppConfig(
        app_dir=app_dir,
        data_dir=data_dir,
        width=width,
        height=height,
        appearance=appearance,
        launchers=_parse_launchers(raw.get("launchers")),
        config_path=used_path,
    )


def write_data_dir_override(app_dir: Path, data_dir: Path) -> Path:
    """Persist data_dir into gitignored config.toml without dropping other keys."""
    path = app_dir / "config.toml"
    assignment = f'data_dir = "{data_dir.resolve().as_posix()}"'
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        if re.search(r"^data_dir\s*=", text, flags=re.MULTILINE):
            text = re.sub(r"^data_dir\s*=.*$", assignment, text, count=1, flags=re.MULTILINE)
        else:
            text = assignment + "\n" + text
    else:
        example = app_dir / "config.example.toml"
        base = example.read_text(encoding="utf-8") if example.is_file() else ""
        text = assignment + "\n" + base
    path.write_text(text, encoding="utf-8")
    return path
