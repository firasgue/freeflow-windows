@echo off
echo ============================================
echo  FreeFlow Windows - EXE Build
echo ============================================
echo.

:: Python und pip prüfen
python --version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python nicht gefunden. Bitte Python 3.10+ installieren.
    pause
    exit /b 1
)

:: Abhängigkeiten installieren
echo [1/3] Installiere Python-Abhängigkeiten...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [2/3] Baue EXE mit PyInstaller...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "FreeFlowWindows" ^
    --hidden-import "pystray._win32" ^
    --hidden-import "win32gui" ^
    --hidden-import "win32api" ^
    --hidden-import "win32con" ^
    --hidden-import "sounddevice" ^
    freeflow_windows.py

echo.
echo [3/3] Fertig!
echo.
echo Die fertige EXE liegt unter:
echo     dist\FreeFlowWindows.exe
echo.
echo Einfach doppelklicken — beim ersten Start wird der Setup-Dialog angezeigt.
echo.
pause
