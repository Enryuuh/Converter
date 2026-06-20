$ErrorActionPreference = "Stop"

$venvPath = ".venv-build"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
  python -m venv $venvPath
}

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r requirements.txt

& $pythonExe -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --collect-data tkinterdnd2 `
  --add-data "assets\converter-logo.png;assets" `
  --add-data "assets\converter-logo.ico;assets" `
  --icon "assets\converter-logo.ico" `
  --name "Converter" `
  app.py

Write-Host ""
Write-Host "EXE creado en: dist\Converter.exe"
