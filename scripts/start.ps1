param([switch]$Dev)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Python environment is missing. Follow README.md setup instructions first.'
}
if (-not $Dev -and -not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) {
    throw 'Frontend build is missing. Run pnpm build from frontend, or use -Dev with the Vite server.'
}
$tempPath = Join-Path $projectRoot '.tmp'
New-Item -ItemType Directory -Force -Path $tempPath | Out-Null
$env:TEMP = $tempPath
$env:TMP = $tempPath
Write-Host 'QORE local server: http://127.0.0.1:8000 · Ctrl+C to stop'
& $pythonPath -m uvicorn qore.main:app --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
