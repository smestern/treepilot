# TreePilot Development Environment Startup Script
# This script starts the Copilot server, backend, and frontend in separate PowerShell windows

Write-Host "Starting TreePilot Development Environment..." -ForegroundColor Green

# Get the script's directory (project root)
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start GitHub Copilot Server in a new PowerShell window if needed
#Write-Host "Launching GitHub Copilot Server..." -ForegroundColor Magenta
#Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'GitHub Copilot Server Starting on port 4321...' -ForegroundColor Magenta; copilot --server --port 4321"

# Wait a moment for Copilot server to start
Start-Sleep -Seconds 3

# Start Backend Server in a new PowerShell window
Write-Host "Launching Backend Server (Python/FastAPI)..." -ForegroundColor Cyan
$BackendPath = Join-Path $ProjectRoot "backend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendPath'; Write-Host 'Backend Server Starting...' -ForegroundColor Green; .\venv\Scripts\python.exe main.py"

# Wait a moment before starting frontend
Start-Sleep -Seconds 2

# Start Frontend Dev Server in a new PowerShell window
Write-Host "Launching Frontend Dev Server (Vite)..." -ForegroundColor Cyan
$FrontendPath = Join-Path $ProjectRoot "frontend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FrontendPath'; Write-Host 'Frontend Dev Server Starting...' -ForegroundColor Green; npm run dev"

Write-Host ""
Write-Host "All services are starting in separate windows!" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:5173 (typical Vite port)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Close the server windows or press Ctrl+C in them to stop the servers." -ForegroundColor Gray
