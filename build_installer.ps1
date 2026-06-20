$ErrorActionPreference = "Stop"

$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
  throw "Inno Setup Compiler (iscc) is not installed. Install Inno Setup 6 or let GitHub Actions build the installer."
}

if (-not $env:APP_VERSION) {
  $env:APP_VERSION = "1.1.0"
}

& $iscc.Source ".\installer\Converter.iss"

Write-Host ""
Write-Host "Instalador creado en: dist\ConverterSetup.exe"
