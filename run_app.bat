@echo off
echo ========================================================
echo Starting Magna AI OEE Engine (CityCare Modern Web App)...
echo ========================================================
cd /d "%~dp0"
start http://localhost:5173
call npm run dev
pause
