@echo off
chcp 65001 >nul
title Cai Dat Thu Vien Cho Tool TikTok
cd /d "%~dp0"
echo ======================================================
echo   DANG CAI DAT CAC THU VIEN PYTHON CAN THIET...
echo ======================================================
pip install -r requirements.txt
echo.
echo Dang cai dat trinh duyet Chromium cho Playwright...
playwright install chromium
echo.
echo ======================================================
echo   DA CAI DAT HOAN TAT! BAN CO THE MO TOOL BANG Chay_Tool.bat
echo ======================================================
pause
