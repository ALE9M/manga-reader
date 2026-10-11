@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Manga Reader non risulta installato.
  echo Esegui prima un doppio clic su setup_windows.bat.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
  echo.
  echo Il programma si e' chiuso con un errore. Controlla il messaggio sopra.
  pause
)
endlocal
