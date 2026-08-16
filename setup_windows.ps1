$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python was not found." -ForegroundColor Red
    Write-Host "Install Python 3.11 or newer from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "During installation, select: Add Python to PATH" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env. The app works in local search mode without an API key." -ForegroundColor Yellow
}

Write-Host "Setup complete. Starting SPOTV Tech Copilot..." -ForegroundColor Green
& ".venv\Scripts\python.exe" -m streamlit run app.py
