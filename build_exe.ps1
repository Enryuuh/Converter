$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$venvPath = Join-Path $repoRoot ".venv-build"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$distDir = Join-Path $repoRoot "dist"
$exePath = Join-Path $distDir "Converter.exe"
$checksumPath = Join-Path $distDir "checksums-sha256.txt"

function Invoke-Native {
  param(
    [Parameter(Mandatory = $true)]
    [scriptblock]$Command,

    [Parameter(Mandatory = $true)]
    [string]$Step
  )

  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "$Step failed with exit code $LASTEXITCODE."
  }
}

function Assert-File {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [Parameter(Mandatory = $true)]
    [string]$Description
  )

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw "$Description not found: $Path"
  }
}

Assert-File -Path (Join-Path $repoRoot "app.py") -Description "Application entry point"
Assert-File -Path (Join-Path $repoRoot "requirements.txt") -Description "Requirements file"
Assert-File -Path (Join-Path $repoRoot "assets\converter-logo.png") -Description "PNG logo"
Assert-File -Path (Join-Path $repoRoot "assets\converter-logo.ico") -Description "ICO logo"

if (-not (Test-Path $pythonExe)) {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if (-not $python) {
    throw "python was not found in PATH. Install Python or add it to PATH before building."
  }

  Invoke-Native -Step "Creating build virtual environment" -Command {
    & $python.Source -m venv $venvPath
  }
}

Assert-File -Path $pythonExe -Description "Build virtual environment Python"

New-Item -ItemType Directory -Path $distDir -Force | Out-Null
Remove-Item -LiteralPath $exePath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $checksumPath -Force -ErrorAction SilentlyContinue

Push-Location $repoRoot
try {
  Invoke-Native -Step "Upgrading pip" -Command {
    & $pythonExe -m pip install --upgrade pip
  }

  Invoke-Native -Step "Installing build dependencies" -Command {
    & $pythonExe -m pip install -r requirements.txt
  }

  Invoke-Native -Step "PyInstaller build" -Command {
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
  }
}
finally {
  Pop-Location
}

if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
  throw "PyInstaller completed without producing the expected artifact: $exePath"
}

Write-Host ""
Write-Host "EXE creado en: $exePath"

$hash = (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  Converter.exe" | Set-Content -LiteralPath $checksumPath -Encoding ascii
Write-Host "Checksum creado en: $checksumPath"
