@echo off
setlocal
cd /d "%~dp0"
title Kuran MP3 SRT - Kurulum

echo.
echo ==========================================
echo    KURAN MP3 SRT - KURULUM (v3)
echo ==========================================
echo.
echo [1/3] FFmpeg kontrol ediliyor...
where ffmpeg >nul 2>&1
if not errorlevel 1 goto ffmpeg_ok
echo [UYARI] FFmpeg bulunamadi veya PATH'de degil.
echo FFmpeg icin 03_FFMPEG_KUR.bat dosyasini kullanabilirsiniz.
echo Kurulumdan sonra bu pencereyi kapatip yeniden acin.
echo.
goto python_control

:ffmpeg_ok
echo [OK] FFmpeg bulundu.
echo.

:python_control
echo [2/3] Python kontrol ediliyor...
if exist ".venv\Scripts\python.exe" goto packages

where py >nul 2>&1
if not errorlevel 1 goto try_py
where python >nul 2>&1
if not errorlevel 1 goto try_python
goto no_python

:try_py
py -3.11 -m venv .venv >nul 2>&1
if not errorlevel 1 goto packages
py -3.12 -m venv .venv >nul 2>&1
if not errorlevel 1 goto packages
py -m venv .venv
if not errorlevel 1 goto packages
goto try_python

:try_python
python -m venv .venv
if not errorlevel 1 goto packages
goto no_python

:packages
if not exist ".venv\Scripts\python.exe" goto no_python
".venv\Scripts\python.exe" --version
if errorlevel 1 goto no_python
echo.
echo [3/3] Kutuphaneler yukleniyor. Internet baglantisi gereklidir.
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto install_failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto install_failed

echo.
echo ==========================================
echo [OK] KURULUM TAMAMLANDI.
echo Simdi 02_BASLAT.bat dosyasini calistirin.
echo ==========================================
pause
exit /b 0

:no_python
echo.
echo [HATA] Python baslatilamadi.
echo CMD icinde su komutu deneyin: py --version
echo Python 3.11 onerilir: https://www.python.org/downloads/
echo Eger Python kuruluysa .venv klasorunu silip yeniden deneyin.
pause
exit /b 1

:install_failed
echo.
echo [HATA] Kutuphaneler kurulurken hata olustu.
echo Ekrandaki son 20 satiri benimle paylasin.
pause
exit /b 1
