@echo off
chcp 65001 >nul
title Tu Dong Cai Dat Moi Truong & Thu Vien - TikTok Channel Tracker
cd /d "%~dp0"

echo ======================================================================
echo   HE THONG TU DONG CAI DAT MOI TRUONG CHO TOOL TIKTOK TRACKER
echo ======================================================================
echo.

:: 1. Kiem tra Python da co tren may chua
set "PY_CMD="
for /f "delims=" %%i in ('python -c "import sys; assert sys.version_info >= (3, 8); print(sys.executable)" 2^>nul') do set "PY_CMD=%%i"
if not "%PY_CMD%"=="" goto :FOUND_PYTHON

for /f "delims=" %%i in ('py -3 -c "import sys; assert sys.version_info >= (3, 8); print(sys.executable)" 2^>nul') do set "PY_CMD=%%i"
if not "%PY_CMD%"=="" goto :FOUND_PYTHON

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
    goto :FOUND_PYTHON
)

:: 2. Neu may chua co Python -> Tu dong tai va cai dat Python 3.11.9 (64-bit)
echo [1/3] May tinh chua cai Python. Dang tu dong tai Python 3.11.9 (chinh hang)...
set "PY_INSTALLER=%TEMP%\python-3.11.9-amd64.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%PY_INSTALLER%'"

if not exist "%PY_INSTALLER%" (
    echo [LOI] Khong the tai Python tu dong. Vui long kiem tra ket noi mang!
    pause
    exit /b 1
)

echo [1/3] Dang tu dong cai dat Python 3.11 (Vui long doi 1-2 phut)...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del /f /q "%PY_INSTALLER%" >nul 2>&1

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
    set "PATH=%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts;%PATH%"
) else (
    set "PY_CMD=python"
)

:FOUND_PYTHON
echo [OK] Da nhan dien moi truong Python: "%PY_CMD%"
echo.
echo [2/3] Dang nang cap pip va cai dat cac thu vien can thiet...
"%PY_CMD%" -m pip install --upgrade pip
"%PY_CMD%" -m pip install -r requirements.txt

echo.
echo [3/3] Dang tai trinh duyet Chromium cho Playwright...
"%PY_CMD%" -m playwright install chromium

if not exist "data" mkdir "data"
echo ok > "data\.playwright_ready"

echo.
echo ======================================================================
echo   CAI DAT HOAN TAT 100%%! DANG TU DONG KHOI DONG TOOL...
echo ======================================================================
start "" wscript.exe //B //Nologo "%~dp0Chay_Tool_Khong_Hien_CMD.vbs"
exit /b 0
