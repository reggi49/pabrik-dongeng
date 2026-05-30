# Pabrik Dongeng - End-to-End Folklore Factory

Repositori ini berisi jalur pipa (pipeline) otomatis untuk membuat video dongeng animasi menggunakan AI.

## 🏗️ Struktur Proyek

- **`script-generator/` (Python):** Otak dari pipeline. Melakukan riset (Brave API), membuat naskah, metadata, prompt gambar, dan skema gerak video (Mimo AI).
- **`video-generator/` (Next.js/Remotion):** Mesin render. Mengambil metadata dan prompt dari `script-generator` untuk merender video animasi menggunakan Remotion.

## 🚀 Alur Kerja (Workflow)

1.  **Generate Assets:** Masuk ke `script-generator`, jalankan `python main_pipeline.py`.
2.  **Verify Outputs:** Pastikan file `.md` dan `.json` sudah muncul di `output_generator/`.
3.  **Render Video:** Copy hasil ke `video-generator/public/dongeng` dan jalankan command render Remotion.

## 🛠️ Git Strategy: Monorepo

Kita menggunakan strategi **Monorepo** agar:
- Perubahan pada skema naskah di Python dapat langsung disinkronkan dengan parser di Next.js.
- History pengembangan fitur animasi dan logika naskah berada di satu timeline yang sama.
- Mempermudah deployment jika nantinya menggunakan CI/CD untuk otomatisasi render.
