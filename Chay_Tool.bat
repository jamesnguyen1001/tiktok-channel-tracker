@echo off
chcp 65001 >nul
title TikTok Channel Growth Tracker
cd /d "%~dp0"

echo ======================================================
echo   DANG KHOI DONG TIKTOK CHANNEL GROWTH TRACKER
echo ======================================================

:: Tim Python tren may
set "PY_CMD="
for /f "delims=" %%i in ('python -c "import sys; assert sys.version_info >= (3, 8); print(sys.executable)" 2^>nul') do set "PY_CMD=%%i"

if "%PY_CMD%"=="" (
    for /f "delims=" %%i in ('py -3 -c "import sys; assert sys.version_info >= (3, 8); print(sys.executable)" 2^>nul') do set "PY_CMD=%%i"
)

if "%PY_CMD%"=="" (
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PY_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
    )
)

:: Neu may chua cai Python hoac chua cai thu vien -> Tu dong chay Cai_Dat_Thu_Vien.bat luon!
if "%PY_CMD%"=="" (
    echo [TU DONG CAI DAT] May chua co Python. Chuyen sang che do tu dong cai dat moi truong...
    call Cai_Dat_Thu_Vien.bat
    exit /b 0
)

"%PY_CMD%" -c "import PyQt6, playwright, openpyxl, requests, PIL, numpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo [TU DONG CAI DAT] Phat hien thieu thu vien tren may moi. Dang tu dong cai dat...
    call Cai_Dat_Thu_Vien.bat
    exit /b 0
)

"%PY_CMD%" app.py
if errorlevel 1 (
    echo.
    echo [LOI] Co loi xay ra. Dang tu dong kiem tra va sua moi truong...
    call Cai_Dat_Thu_Vien.bat
)
