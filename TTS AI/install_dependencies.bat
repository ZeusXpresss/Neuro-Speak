@echo off
title TTS Program Setup
echo =====================================================
echo        Installing Dependencies for TTS Program
echo =====================================================
echo.

:: =====================================================
:: PRE-REQUISITE CHECKS (Python 3.10 EXACTLY and eSpeak-NG)
:: =====================================================

:: --- 1. Check for Python 3.10 (Exactly) ---
echo.
echo [1/2] Checking for Python 3.10 exactly...

python --version >nul 2>&1
if %errorlevel% neq 0 goto :INSTALL_PYTHON_MISSING

:: Get major and minor version numbers
:: This uses the output of 'python --version' (e.g., Python 3.10.6)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i

:: Parse version string (e.g., 3.10.6 -> Major=3, Minor=10)
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PYTHON_MAJOR=%%a
    set PYTHON_MINOR=%%b
)

:: Normalize version numbers for numerical comparison (e.g., 3.10 -> 310)
set /a PYTHON_VERSION_CODE=%PYTHON_MAJOR% * 100 + %PYTHON_MINOR%

:: Check if the code is NOT exactly 310
if not %PYTHON_VERSION_CODE% EQU 310 goto :INSTALL_PYTHON_WRONG_VERSION

echo [SUCCESS] Exact Python version 3.10 found.
goto :CHECK_NGSPEAK

:INSTALL_PYTHON_MISSING
echo [ERROR] Python not found.
echo Please install Python 3.10 from:
echo   https://www.python.org/downloads/
echo (Ensure "Add Python to PATH" is checked during installation.)
echo.
pause
exit /b

:INSTALL_PYTHON_WRONG_VERSION
echo [ERROR] Python 3.10 is required. Detected version: %PYTHON_VERSION%
echo Please install Python 3.10 from:
echo   https://www.python.org/downloads/
echo (Ensure "Add Python to PATH" is checked during installation.)
echo.
pause
exit /b

:: --- 2. Check for NG-Speak (eSpeak-NG) ---
:CHECK_NGSPEAK
echo.
echo [2/2] Checking for NG-Speak (eSpeak-NG)...

:: Check for the presence of the espeak-ng executable in PATH
where espeak-ng >nul 2>&1
if %errorlevel% neq 0 (
    goto :INSTALL_NGSPEAK
)

echo [SUCCESS] NG-Speak (espeak-ng) found.

:: --- 3. Prompt for Visual Studio Build Tools ---
echo.
echo =====================================================
echo IMPORTANT: Visual Studio Build Tools Required
echo =====================================================
echo Some dependencies require C++ build tools (Visual Studio Build Tools).
echo If you have not done so, please install them now.
echo 1. Download the Build Tools from Microsoft:
echo    https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
echo 2. During installation, select the "Desktop Development with C++" workload.
echo -----------------------------------------------------
echo PRESS ANY KEY TO PROCEED WITH PYTHON INSTALLATION...
pause >nul
goto :INSTALL_PYTHON_DEPS

:INSTALL_NGSPEAK
echo [ERROR] NG-Speak (eSpeak-NG) is required for TTS functionality.
echo Please download and install the latest Windows installer from:
echo   https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0
echo.
pause
exit /b

:: =====================================================
:: PYTHON DEPENDENCY INSTALLATION
:: (Skipped if pre-requisites fail)
:: =====================================================
:INSTALL_PYTHON_DEPS

:: --- Upgrade pip ---
echo [1/5] Upgrading pip...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b
)

:: --- Install PyTorch (with CUDA if available) ---
echo [2/5] Installing PyTorch (this may take several minutes)...
python -m pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121
if %errorlevel% neq 0 (
    echo [WARNING] PyTorch GPU build may not be compatible. Retrying with CPU version...
    python -m pip install torch torchvision torchaudio
)

:: --- Install TTS and Other Core Libraries ---
echo [3/5] Installing core Python packages...
python -m pip install TTS sounddevice numpy pyautogui keyboard pillow pytesseract opencv-python pynput
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install core dependencies.
    pause
    exit /b
)

:: --- Install UI/Visual Libraries ---
echo [4/5] Installing GUI enhancements...
python -m pip install ttkbootstrap
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install ttkbootstrap.
    pause
    exit /b
)

:: --- Installation Summary ---
echo.
echo =====================================================
echo [SUCCESS] All Python dependencies installed.
echo =====================================================
echo.
echo =====================================================
echo NOTE:
echo   You still need to install Tesseract OCR manually.
echo   Download it from: https://github.com/UB-Mannheim/tesseract/wiki
echo   Default path expected by your program:
echo   C:\Program Files\Tesseract-OCR\tesseract.exe
echo =====================================================
echo.

pause