$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$destination = Join-Path (Split-Path $PSScriptRoot -Parent) "SPOTV-Trouble-AI.zip"
$temporary = Join-Path $env:TEMP ("spotv-export-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $temporary | Out-Null
Get-ChildItem -Force | Where-Object { $_.Name -notin @('.git','.venv','.env','__pycache__','.pytest_cache','spotv_trouble.db') } | Copy-Item -Destination $temporary -Recurse
if (Test-Path $destination) { Remove-Item -LiteralPath $destination }
Compress-Archive -Path (Join-Path $temporary '*') -DestinationPath $destination
Remove-Item -LiteralPath $temporary -Recurse -Force
Write-Host "생성 완료: $destination"

