@echo off
title TTS Program Setup
echo =====================================================
echo        Installing Dependencies for TTS Program
echo =====================================================
echo.

:: --- Check Python Installation ---
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found.
    echo Please install Python 3.9 or higher from:
    echo   https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b
)

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
echo   Download it from:
echo     https://github.com/UB-Mannheim/tesseract/wiki
echo   Default path expected by your program:
echo     C:\Program Files\Tesseract-OCR\tesseract.exe
echo =====================================================
echo.

pause
