param(
  [Parameter(Mandatory = $true)]
  [string]$FilePath,

  [switch]$RequireSigning
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $FilePath)) {
  throw "File not found: $FilePath"
}

if (-not $env:WINDOWS_CERTIFICATE_BASE64 -or -not $env:WINDOWS_CERTIFICATE_PASSWORD) {
  if ($RequireSigning) {
    throw "Signing is required, but WINDOWS_CERTIFICATE_BASE64 or WINDOWS_CERTIFICATE_PASSWORD is not set."
  }
  Write-Host "Skipping signing: WINDOWS_CERTIFICATE_BASE64 or WINDOWS_CERTIFICATE_PASSWORD is not set."
  exit 0
}

$certificatePath = Join-Path $env:TEMP ("converter-signing-{0}.pfx" -f ([Guid]::NewGuid().ToString("N")))

$signtool = Get-Command signtool -ErrorAction SilentlyContinue
if (-not $signtool) {
  $kitRoot = "${env:ProgramFiles(x86)}\Windows Kits\10\bin"
  $signtool = Get-ChildItem -Path $kitRoot -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1
}

if (-not $signtool) {
  throw "signtool.exe was not found."
}

try {
  [IO.File]::WriteAllBytes($certificatePath, [Convert]::FromBase64String($env:WINDOWS_CERTIFICATE_BASE64))

  & $signtool.Source sign `
    /fd SHA256 `
    /td SHA256 `
    /tr http://timestamp.digicert.com `
    /f $certificatePath `
    /p $env:WINDOWS_CERTIFICATE_PASSWORD `
    $FilePath

  & $signtool.Source verify /pa /v $FilePath
}
finally {
  Remove-Item -LiteralPath $certificatePath -Force -ErrorAction SilentlyContinue
}
