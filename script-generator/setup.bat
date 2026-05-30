@echo off
TITLE Pabrik Dongeng - Windows Setup

echo 🚀 Memulai setup lingkungan untuk Pabrik Dongeng...

:: 1. Cek Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python tidak ditemukan di PATH. Silakan instal Python 3.9+ dan centang 'Add to PATH'.
    pause
    exit /b
)

:: 2. Membuat Virtual Environment
if not exist "env_dongeng" (
    echo 📦 Membuat virtual environment 'env_dongeng'...
    python -m venv env_dongeng
) else (
    echo ✅ Virtual environment 'env_dongeng' sudah ada.
)

:: 3. Install Dependencies
echo 📥 Melakukan instalasi requirements...
call env_dongeng\Scripts\activate
python -m pip install --upgrade pip
pip install requests python-dotenv

:: 4. Inisialisasi .env
if not exist ".env" (
    echo 📝 Membuat file .env boilerplate...
    echo MIMO_API_KEY=isi_di_sini > .env
    echo BRAVE_API_KEY=isi_di_sini >> .env
    echo ⚠️  Jangan lupa isi kunci API di dalam file .env!
) else (
    echo ✅ File .env sudah ada.
)

:: 5. Folder Struktur
if not exist "debug_logs" mkdir debug_logs
if not exist "output_generator" mkdir output_generator

echo --------------------------------------------------------
echo ✅ Setup Selesai!
echo Untuk menjalankan pipeline, gunakan:
echo call env_dongeng\Scripts\activate ^&^& python main_pipeline.py
echo --------------------------------------------------------
pause
