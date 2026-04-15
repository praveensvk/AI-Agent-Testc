@echo off
REM Start E-Commerce Application on Windows

echo.
echo ====================================
echo   TechStore E-Commerce App Startup
echo ====================================
echo.

REM Check if Node.js is installed
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

echo Starting Backend (Port 5000)...
cd /d "%~dp0backend"

REM Install dependencies if node_modules doesn't exist
if not exist node_modules (
    echo Installing backend dependencies...
    call npm install
)

REM Start backend in a new window
start "Backend - TechStore" cmd /k "npm start"

echo.
echo Waiting 3 seconds before starting frontend...
timeout /t 3 /nobreak

echo Starting Frontend (Port 3000)...
cd /d "%~dp0frontend"

REM Install dependencies if node_modules doesn't exist
if not exist node_modules (
    echo Installing frontend dependencies...
    call npm install
)

REM Start frontend
start "Frontend - TechStore" cmd /k "npm start"

echo.
echo ====================================
echo   Services Starting...
echo ====================================
echo.
echo Backend:  http://localhost:5000
echo Frontend: http://localhost:3000
echo.
echo Test Credentials:
echo   Email:    test@example.com
echo   Password: password123
echo.
echo Press any key to exit (closes both terminal windows)...
pause

REM Kill all npm processes
taskkill /F /IM node.exe 2>nul

echo All services stopped.
pause
