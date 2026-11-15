@echo off
chcp 65001 >nul
title TikTok Channel Growth Tracker
cd /d "%~dp0"
echo ======================================================
echo   DANG KHOI DONG TIKTOK CHANNEL GROWTH TRACKER
echo ======================================================
python app.py
if errorlevel 1 (
    echo.
    echo [LOI] Khong the khoi dong ung dung. Vui long chay file Cai_Dat_Thu_Vien.bat truoc!
    pause
)
