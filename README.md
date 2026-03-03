# Sistem Deteksi Manipulasi Gambar (ImageGuard)

Aplikasi berbasis web untuk mendeteksi manipulasi gambar dengan fitur filter privasi dan pencarian kemiripan gambar baik secara lokal maupun fallback ke web.

## Arsitektur & Teknologi

Proyek ini dibangun menggunakan arsitektur Client-Server (REST API) dengan teknologi berikut:

### Frontend
- Framework: React 18
- Build Tool: Vite 5
- Styling: Tailwind CSS v3 (Dark Glassmorphism)
- HTTP Client: Axios

### Backend
- Framework: Django 5.x
- API Layer: Django REST Framework (DRF)
- Database: PostgreSQL (dengan fallback SQLite)
- Machine Learning: PyTorch (MobileNetV2, Feature Extraction)
- Layanan Eksternal: Google Cloud Vision API

## Fitur Utama

### 1. Sistem Machine Learning (Kemiripan Gambar)
Sistem ini menggunakan arsitektur PyTorch CNN (MobileNetV2) yang dikonfigurasi khusus tanpa classifier akhir. Model ini diload secara lazy (singleton mode) dengan deteksi GPU (CUDA) secara otomatis otomatis untuk memproses ekstraksi feature secepat mungkin. 

Pipeline pemrosesan gambar meliputi:
- Resize dimensi ke 224x224 (RGB)
- Normalisasi tensor berbasis standard metrik ImageNet
- No-Gradient Mode untuk efisiensi memorI RAM/VRAM
- Transformasi vektor 1280-dimensi (dikompresi jadi unit length dengan L2 Normalization)
- Perbandingan dua buah file image menggunakan perhitungan _Cosine Similarity_

### 2. Filter Privasi (Privacy Service)
Sebelum sebuah gambar diproses untuk pengecekan web/lokal, backend akan menganalisis konten menggunakan text rules & Google Cloud Vision. Sistem berhak memberikan status `Blocked` jika terdapat sekurang kurangnya 3 dari kategori ini dalam sebuah input yang sama:
- Wajah
- Nama (berbasis pola huruf kapital)
- Umur (berbasis pola numerik + kata kunci)
- Alamat Lengkap (Kecamatan, RT/RW, dsb)
- Nomor Telepon genggam (+62 atau 08x)

### 3. Frontend Admin Dashboard & User Searching
- Halaman user biasa dilengkapi status "Deteksi Doksli" atau pencocokan via Google
- Modul Admin Dashboard khusus (`/admin`) dilengkapi dengan form otentikasi (username: admin) untuk mendaftarkan dokumen baru maupun menghapus data.

## Struktur Database
Sistem ini menyimpan data menggunakan PostgreSQL. Tabel utamanya meliputi:
- **OriginalDocument**: Menyediakan embedding base array dan info file untuk referensi (Doksli)
- **SearchResult**: Hasil similarity calculation baik via lokal database maupun url external
- **PrivacyAnalysis**: Mencatat report sensor/privasi per transaksi Upload
- **SearchQuery**: Jejak upload harian
- **DocumentLabel**: Label hasil parsing OCR

## Menjalankan Proyek Secara Lokal

Jika Anda baru melakukan klona pada proyek ini:

1. **Jalankan Backend (Django Server)**
   Pastikan Anda telah mendefinisikan URL Postgree pada file variable Environtmet `.env` yang berada di direktori `backend` dan telah berhasil men-set `pyTorch` requirement.
   ```bash
   cd backend
   python manage.py runserver
   ```

2. **Jalankan Frontend (React + Vite)**
   Masuk ke module Vite (Front End) pada terminal terpisah lalu trigger web server dev nya.
   ```bash
   cd frontend
   npm run dev
   ```

## API Access Reference
Beberapa _routing_ utama pada sistem ini diantaranya:
- `POST /api/search/` (User Upload Query)
- `POST /api/add-original/` (Add Dokumen via Admin Panel)
- `GET /api/originals/` (Admin Panel Dokumen Líst)
- `POST /api/admin/login/` (Endpoint khusus Authenticator Admin)

(Seluruh sistem ini diharapkan berjalan otomatis pada environment CPU maupun GPU tanpa harus melalui step Fine-Tuning atau pelatihan Model (Model Training)).
