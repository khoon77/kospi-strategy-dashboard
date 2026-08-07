$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$config = Join-Path $PSScriptRoot 'config.json'
if (-not (Test-Path $config)) {
    Copy-Item (Join-Path $PSScriptRoot 'config.example.json') $config
}
Set-Location $repo
if (-not (Test-Path '.venv')) { py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r crypto_collector\requirements.txt
Start-Process -WindowStyle Hidden -FilePath '.\.venv\Scripts\python.exe' -ArgumentList 'crypto_collector\api.py','--config','crypto_collector\config.json'
& .\.venv\Scripts\python.exe crypto_collector\collector.py --config crypto_collector\config.json

