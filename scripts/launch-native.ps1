$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Test-AudioPython($candidate) {
  if (-not $candidate -or -not (Test-Path $candidate)) {
    return $false
  }

  & $candidate -c "import sounddevice, numpy" *> $null
  return $LASTEXITCODE -eq 0
}

$candidates = @(
  "C:\ProgramData\miniconda3\python.exe",
  (Get-Command python -ErrorAction SilentlyContinue).Source,
  "C:\Python314\python.exe"
) | Where-Object { $_ } | Select-Object -Unique

$python = $candidates | Where-Object { Test-AudioPython $_ } | Select-Object -First 1
if (-not $python) {
  $python = $candidates | Select-Object -First 1
}

Start-Process -FilePath $python `
  -ArgumentList "src\desktop\practice_float.py" `
  -WorkingDirectory $root
