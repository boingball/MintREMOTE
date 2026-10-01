$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
py -3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Python 3 is required to build the client." }
$Python = Join-Path $PWD ".venv\Scripts\python.exe"
& $Python -m pip install -r viewer/requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Client tests failed." }
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name MintREMOTE --paths viewer viewer/mintremote_viewer.py
if ($LASTEXITCODE -ne 0) { throw "Windows build failed." }
Write-Host "Built $PWD\dist\MintREMOTE.exe"
