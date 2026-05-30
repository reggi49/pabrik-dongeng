#!/bin/bash

# Pabrik Dongeng - Environment Setup Script (macOS/Linux)
# -------------------------------------------------------

echo "🚀 Memulai setup lingkungan untuk Pabrik Dongeng..."

# 1. Cek Python
if ! command -v python3 &> /dev/null
then
    echo "❌ Python3 tidak ditemukan. Silakan instal Python 3.9+ terlebih dahulu."
    exit 1
fi

# 2. Membuat Virtual Environment (jika belum ada)
if [ ! -d "env_dongeng" ]; then
    echo "📦 Membuat virtual environment 'env_dongeng'..."
    python3 -m venv env_dongeng
else
    echo "✅ Virtual environment 'env_dongeng' sudah ada."
fi

# 3. Upgrade Pip & Install Dependencies
echo "📥 Melakukan instalasi requirements..."
./env_dongeng/bin/pip install --upgrade pip
./env_dongeng/bin/pip install requests python-dotenv

# 4. Inisialisasi .env (jika belum ada)
if [ ! -f ".env" ]; then
    echo "📝 Membuat file .env boilerplate..."
    echo "MIMO_API_KEY=isi_di_sini" > .env
    echo "BRAVE_API_KEY=isi_di_sini" >> .env
    echo "⚠️  Jangan lupa isi kunci API di dalam file .env!"
else
    echo "✅ File .env sudah ada."
fi

# 5. Membuat folder yang dibutuhkan
mkdir -p debug_logs
mkdir -p output_generator

echo "--------------------------------------------------------"
echo "✅ Setup Selesai!"
echo "Untuk menjalankan pipeline, gunakan:"
echo "source env_dongeng/bin/activate && python3 main_pipeline.py"
echo "--------------------------------------------------------"
