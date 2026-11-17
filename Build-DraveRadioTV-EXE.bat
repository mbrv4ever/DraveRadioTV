@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==== DraveRadio ^& TV - EXE bouwen ====
py -3.12 -c "import PyQt6.QtMultimedia, neuvoice, onnxruntime, certifi" || (echo FOUT: py -3.12 mist PyQt6/neuvoice/onnxruntime/certifi & pause & exit /b 1)
py -3.12 -m PyInstaller --noconfirm --clean --onedir --windowed --name DraveRadioTV --icon assets\icon.ico ^
  --add-data "assets;assets" --hidden-import bronnen --hidden-import leon ^
  --collect-all neuvoice --collect-all onnxruntime --collect-data certifi ^
  --exclude-module torch --exclude-module torchvision --exclude-module torchaudio --exclude-module tensorflow ^
  --exclude-module transformers --exclude-module matplotlib --exclude-module pandas --exclude-module scipy ^
  --exclude-module PyQt6.QtWebEngineCore --exclude-module tkinter radiotv.py
if errorlevel 1 (echo FOUT: PyInstaller is mislukt & pause & exit /b 1)
if not exist "dist\DraveRadioTV\DraveRadioTV.exe" (echo FOUT: geen exe gemaakt & pause & exit /b 1)
xcopy /E /I /Y assets "dist\DraveRadioTV\assets" >nul
echo.
echo KLAAR: dist\DraveRadioTV\DraveRadioTV.exe
pause
