@echo off
setlocal
cd /d "%~dp0"
title Kuran MP3 SRT - Baslat
if not exist ".venv\Scripts\python.exe" goto no_install
".venv\Scripts\python.exe" "kuran_mp3_srt.py"
if errorlevel 1 goto failed
exit /b 0

:no_install
echo [HATA] Once 01_KURULUM.bat dosyasini calistirin.
pause
exit /b 1

:failed
echo.
echo [HATA] Uygulama acilamadi. Yukaridaki hata mesajini paylasin.
pause
exit /b 1
