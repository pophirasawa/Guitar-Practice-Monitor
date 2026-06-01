$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Test-BuildPython($candidate) {
  if (-not $candidate -or -not (Test-Path $candidate)) {
    return $false
  }
  & $candidate -c "import sounddevice, numpy, tkinter" *> $null
  return $LASTEXITCODE -eq 0
}

$candidates = @(
  "C:\ProgramData\miniconda3\python.exe",
  (Get-Command python -ErrorAction SilentlyContinue).Source
) | Where-Object { $_ } | Select-Object -Unique

$python = $candidates | Where-Object { Test-BuildPython $_ } | Select-Object -First 1
if (-not $python) {
  throw "No Python with sounddevice, numpy, and tkinter was found."
}

& $python "$root\scripts\generate_icon.py"

Push-Location "$root\packaging"
try {
  & $python -m PyInstaller --clean --noconfirm "practice_float.spec" --distpath "$root\dist" --workpath "$root\build"
} finally {
  Pop-Location
}

$bundle = "$root\dist\GuitarPracticeMonitor"
New-Item -ItemType Directory -Force -Path "$bundle\data" | Out-Null
Move-Item -Force "$root\dist\guitar-practice-monitor.exe" "$bundle\guitar-practice-monitor.exe"
if (Test-Path "$root\data\practice_log.json") {
  Copy-Item -Force "$root\data\practice_log.json" "$bundle\data\practice_log.json"
} else {
  "{}" | Set-Content -Encoding UTF8 "$bundle\data\practice_log.json"
}

Write-Host "Built: $bundle"
