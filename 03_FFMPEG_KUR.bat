@echo off
setlocal
cd /d "%~dp0"
title FFmpeg Kurulumu
where winget >nul 2>&1
if errorlevel 1 goto no_winget
echo FFmpeg Windows paket yoneticisi ile yukleniyor...
winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto failed
echo.
echo Kurulum tamamlandi. Tum CMD pencerelerini kapatin.
echo Sonra 01_KURULUM.bat dosyasini yeniden acin.
pause
exit /b 0

:no_winget
echo [HATA] winget bulunamadi.
echo FFmpeg icin: https://ffmpeg.org/download.html
pause
exit /b 1

:failed
echo [HATA] FFmpeg yuklenemedi. Hatayi kontrol edin.
pause
exit /b 1
