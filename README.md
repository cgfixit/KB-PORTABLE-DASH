# KB-GUI-Lite

Offline, LAN-shareable helpdesk console for a tech sitting on a ticket.

A single CustomTkinter window over local SQLite + CSV files. Copy the folder onto a share, run it, keep working if the internet is down.

## What it is

- A fast desktop console: board, knowledge base, launchers, admin refs
- Data next to the app (or one folder you choose)
- CSV import/export so a tech can still dump/share a folder
- Windows-first, then macOS/Linux

## What it is not

- Not SaaS, not IT Glue, not CyClaw
- Not multi-user sync, Dropbox, or git-as-a-database
- Not a password manager, SSO, or cloud auth
- No telemetry, no installer in this tree

## Run (Windows / PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m kbgui
```

Or: `python main.py` from the repo root after the same install.

## Run (macOS / Linux)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m kbgui
```

Needs Python 3.12+ with Tk (`python3 -c "import tkinter"`). On macOS, Homebrew `python@3.12` includes Tk. Pyenv builds often do not.

## Data-dir contract

Resolve once, in this order:

1. Environment variable `KB_GUI_DATA_DIR`
2. `data_dir` in `config.toml` next to `main.py`
3. Directory containing `main.py` / the executable

SQLite lives at `<data_dir>/data/kb.sqlite`. First run copies `examples/*.example.csv` into that `data/` folder (gitignored) and imports them.

Copy `config.example.toml` to `config.toml` to set window size, theme, launchers, and an optional `data_dir`. `config.toml` is gitignored.

Footer **Edit data folder** writes `data_dir` into local `config.toml` and reloads.

## Secrets

Firewall / O365 / creds password columns are optional and shown masked.

- CSV and sqlite store **non-secret fields only** (customer, URL, username, …)
- Passwords persist only in the OS store (Windows Credential Manager / macOS Keychain)
- If the OS store is unavailable, the app **refuses to save the password** and says so in the UI
- There is no application-level encryption of plaintext passwords

Never put live passwords, API keys, or customer rows in git. Only `*.example.csv` templates are tracked.

## Screenshot

Add a local PNG at `docs/screenshot.png` if you want a picture in this README. Do not hotlink screenshots.

## Tests / lint

```bash
pip install -e ".[dev]"
ruff check .
pytest
```
