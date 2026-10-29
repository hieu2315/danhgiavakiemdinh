$ErrorActionPreference = "Stop"
$env:RELOOP_HOST = "127.0.0.1"
$env:RELOOP_PORT = "8000"
$env:RELOOP_ENV = "development"
$env:RELOOP_DB = Join-Path $PSScriptRoot "..\reloop.sqlite3"
$env:RELOOP_ADMIN_EMAIL = "admin@reloop.local"
$env:RELOOP_ADMIN_PASSWORD = "ReLoopAdmin-Local-2026!"
Write-Warning "Local demo only. Do not expose this demo account or server to the Internet."
Set-Location (Join-Path $PSScriptRoot "..")
python scripts\seed_demo.py
if ($LASTEXITCODE -ne 0) { throw "Không tạo được dữ liệu demo." }
python server.py
