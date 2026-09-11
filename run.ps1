# Windows launcher for KB-Portable-DASH. Run from anywhere:
#   powershell -File .\run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0) { return }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
        if ($LASTEXITCODE -eq 0) {
            python -c "import sys; print(sys.executable)"
            return
        }
    }
    throw "Python 3.12+ is required. Install from https://www.python.org/downloads/windows/ (check Tcl/Tk) and retry."
}

$python = (Find-Python).Trim()
& $python -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Tkinter is missing. Reinstall Python 3.12 from python.org and enable Tcl/Tk. Needed on Windows 10 and 11."
}
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    & $python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\python.exe -m kbgui
