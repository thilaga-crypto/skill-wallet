Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env. Add your Gemini API key before continuing."
    notepad ".env"
    Read-Host "Press Enter after saving .env"
}

Start-Process "http://127.0.0.1:5050/generate-workout"
& ".venv\Scripts\python.exe" app.py
