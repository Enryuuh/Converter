$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$distDir = Join-Path $repoRoot "dist"
$exePath = Join-Path $distDir "Converter.exe"
$setupPath = Join-Path $distDir "ConverterSetup.exe"
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

$isccCommand = Get-Command iscc -ErrorAction SilentlyContinue
$isccPath = if ($isccCommand) { $isccCommand.Source } else { $null }

if (-not $isccPath) {
  $innoCandidates = @()
  if (${env:ProgramFiles(x86)}) {
    $innoCandidates += Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
  }
  if ($env:ProgramFiles) {
    $innoCandidates += Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"
  }
  $isccPath = $innoCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}

if (-not $isccPath) {
  throw "Inno Setup Compiler (iscc) was not found. Install Inno Setup 6, add iscc to PATH, or let GitHub Actions build the installer."
}

if (-not $env:APP_VERSION) {
  $appPyPath = Join-Path $repoRoot "app.py"
  $versionMatch = Select-String -LiteralPath $appPyPath -Pattern '^APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
  if (-not $versionMatch) {
    throw "APP_VERSION was not provided and could not be read from $appPyPath."
  }
  $env:APP_VERSION = $versionMatch.Matches[0].Groups[1].Value
}

if ($env:APP_VERSION -notmatch '^\d+\.\d+\.\d+$') {
  throw "Invalid APP_VERSION '$env:APP_VERSION'. Expected format: X.Y.Z"
}

if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
  throw "Missing executable for installer build: $exePath. Run .\build_exe.ps1 first."
}

New-Item -ItemType Directory -Path $distDir -Force | Out-Null
Remove-Item -LiteralPath $setupPath -Force -ErrorAction SilentlyContinue

Push-Location $repoRoot
try {
  Invoke-Native -Step "Inno Setup" -Command {
    & $isccPath ".\installer\Converter.iss"
  }
}
finally {
  Pop-Location
}

if (-not (Test-Path -LiteralPath $setupPath -PathType Leaf)) {
  throw "Inno Setup completed without producing the expected artifact: $setupPath"
}

Write-Host ""
Write-Host "Instalador creado en: $setupPath"

$artifacts = @(
  [pscustomobject]@{ Path = $exePath; Name = "Converter.exe" },
  [pscustomobject]@{ Path = $setupPath; Name = "ConverterSetup.exe" }
)

$checksumLines = foreach ($artifact in $artifacts) {
  $hash = (Get-FileHash -LiteralPath $artifact.Path -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $($artifact.Name)"
}

$checksumLines | Set-Content -LiteralPath $checksumPath -Encoding ascii
Write-Host "Checksums actualizados en: $checksumPath"
