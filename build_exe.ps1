$ErrorActionPreference = "Stop"

python -m pip install -r requirements.txt

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --collect-data tkinterdnd2 `
  --add-data "assets\converter-logo.png;assets" `
  --icon "assets\converter-logo.ico" `
  --name "Converter" `
  app.py

Write-Host ""
Write-Host "EXE creado en: dist\Converter.exe"
