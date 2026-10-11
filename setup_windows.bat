@echo off
setlocal
cd /d "%~dp0"
echo.
echo Manga Reader - installazione automatica
echo Si aprira' PowerShell per installare i componenti necessari.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
if errorlevel 1 (
  echo.
  echo Installazione non completata. Leggi il messaggio qui sopra e riprova.
  pause
)
endlocal
