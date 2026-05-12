# Aplikasi Pencari Doksli — Sistem Deteksi Manipulasi Gambar

![Screenshot Aplikasi](screenshot.png)

**Aplikasi Pencari Doksli** (Dokumen Asli) adalah aplikasi berbasis web untuk mendeteksi manipulasi gambar dengan fitur filter privasi otomatis dan pencarian kemiripan gambar menggunakan teknologi _Machine Learning_. Sistem ini mampu membandingkan gambar yang diunggah pengguna terhadap database dokumen asli secara lokal maupun melalui pencarian web menggunakan Google Cloud Vision API.

---

## Daftar Isi

- [Arsitektur Sistem](#-arsitektur-sistem)
- [Tech Stack](#-tech-stack)
- [Fitur Utama](#-fitur-utama)
- [Struktur Proyek](#-struktur-proyek)
- [Struktur Database](#-struktur-database)
- [Service Layer (Backend)](#-service-layer-backend)
- [Komponen Frontend](#-komponen-frontend)
- [API Endpoints](#-api-endpoints)
- [Instalasi & Menjalankan Proyek](#-instalasi--menjalankan-proyek)
- [Environment Variables](#-environment-variables)
- [Management Commands](#-management-commands)

---

## Arsitektur Sistem

Proyek ini dibangun menggunakan arsitektur **Client-Server (REST API)** dengan pemisahan yang jelas antara lapisan frontend dan backend.

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + Vite)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │SearchPage│ │ResultPage│ │AdminPage │ │OriginalsPage  │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬────────┘  │
│       └─────────────┴────────────┴──────────────┘           │
│                         Axios HTTP Client                   │
└────────────────────────────┬────────────────────────────────┘
                             │ REST API (JSON)
┌────────────────────────────┴────────────────────────────────┐
│                   BACKEND (Django + DRF)                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   API Layer (Views)                  │    │
│  └──────┬──────────┬──────────┬──────────┬─────────────┘    │
│         │          │          │          │                   │
│  ┌──────▼───┐ ┌────▼────┐ ┌──▼─────┐ ┌─▼──────────────┐   │
│  │ Privacy  │ │Embedding│ │Similari│ │ Vision Service │   │
│  │ Service  │ │ Service │ │  ty    │ │ (Google Cloud) │   │
│  └──────────┘ └─────────┘ └────────┘ └────────────────┘   │
│         │          │          │          │                   │
│  ┌──────▼──────────▼──────────▼──────────▼─────────────┐   │
│  │          PostgreSQL Database (UUID PKs)              │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Frontend
| Teknologi | Versi | Fungsi |
|-----------|-------|--------|
| **React** | 18.2 | Library UI berbasis komponen |
| **Vite** | 5.x | Build tool & dev server (HMR) |
| **Tailwind CSS** | 3.4 | Utility-first CSS framework |
| **React Router DOM** | 6.20 | Client-side routing (SPA) |
| **Axios** | 1.6 | HTTP client untuk komunikasi API |

### Backend
| Teknologi | Versi | Fungsi |
|-----------|-------|--------|
| **Django** | 5.x | Web framework utama |
| **Django REST Framework** | 3.14+ | Serializer & API views |
| **PostgreSQL** | 15+ | Database relasional utama |
| **PyTorch** | 2.0+ | Framework deep learning (MobileNetV2) |
| **TorchVision** | 0.15+ | Pre-trained CNN models & transforms |
| **OpenCV** | 4.8+ | Deteksi wajah (Haar Cascade) |
| **EasyOCR** | latest | Ekstraksi teks dari gambar (OCR) |
| **Google Cloud Vision API** | 3.5+ | Face detection, OCR, Web detection |
| **Pillow** | 10.0+ | Manipulasi gambar (resize, crop) |
| **NumPy** | 1.24+ | Operasi matriks & vektor |
| **psycopg2** | 2.9+ | PostgreSQL adapter untuk Python |
| **python-dotenv** | 1.0+ | Environment variable loader |

### DevOps & Tooling
| Teknologi | Fungsi |
|-----------|--------|
| **Git + GitHub** | Version control & repository hosting |
| **PostCSS + Autoprefixer** | CSS post-processing |
| **Vite Proxy** | Proxy `/api` & `/media` ke Django dev server |

---

## Fitur Utama

### 1. Pencarian Kemiripan Gambar (Image Similarity Search)

Sistem menggunakan arsitektur **CNN MobileNetV2** (PyTorch) yang dikonfigurasi khusus tanpa _classifier_ akhir untuk menghasilkan _feature embedding_ dari setiap gambar.

**Pipeline Pemrosesan:**
1. Gambar di-resize ke `224×224` piksel (RGB)
2. Normalisasi tensor menggunakan standar metrik ImageNet
3. Inferensi dilakukan dalam `torch.no_grad()` mode (efisiensi memori)
4. Menghasilkan vektor **1280-dimensi** yang di-normalisasi L2 (_unit length_)
5. Perbandingan menggunakan perhitungan **Cosine Similarity** (0.0 – 1.0)

**Fitur Teknis:**
- Auto-deteksi GPU (CUDA) untuk akselerasi inferensi, _fallback_ ke CPU
- _Singleton model loading_ (model diload sekali, digunakan berulang)
- Deduplikasi file menggunakan SHA-256 hash

### 2. Filter Privasi Otomatis (Privacy Analysis)

Sebelum gambar diproses untuk pengecekan kemiripan, backend menganalisis konten untuk melindungi data pribadi. Sistem memberikan status **Blocked** jika terdeteksi ≥ 3 dari 5 kategori berikut:

| Kategori | Metode Deteksi | Keterangan |
|----------|---------------|------------|
| **Wajah** | OpenCV Haar Cascade + Histogram Equalization | Deteksi wajah dengan preprocessing kontras otomatis |
| **Nama** | Regex berbasis indikator kata kunci | Mendeteksi label "Nama:", "Name:", termasuk _typo_ OCR ("Narna", "Noma") |
| **Umur** | Regex pola numerik + kata kunci | Mendeteksi pola `XX tahun/thn/th` dan format Tempat Tanggal Lahir |
| **Alamat** | Regex _word-boundary_ berlapis | Membutuhkan ≥ 2 kata kunci alamat unik (Jalan, RT/RW, Kecamatan, dll.) |
| **No. Identitas** | Regex 16-digit agresif | Mendeteksi NIK KTP tanpa memerlukan label "NIK" (resilien terhadap OCR _noise_) |

**Strategi Deteksi Berlapis:**
- **Google Cloud Vision API** → _fallback_ ke **OpenCV/EasyOCR** (lokal)
- **Histogram Equalization** otomatis untuk menangani gambar berkontras rendah
- **Konteks-Cerdas (Context-Aware):** Deteksi _header_ KTP (`PROVINSI...NIK`) untuk inferensi logis

### 3. Perbandingan Visual Side-by-Side

Ketika sistem menemukan lebih dari satu kecocokan, pengguna dapat mengklik hasil untuk membuka **modal perbandingan** yang menampilkan gambar _query_ dan dokumen asli (_Doksli_) secara berdampingan, lengkap dengan skor kecocokan.

### 4. Admin Dashboard

Panel admin (`/admin`) dilengkapi dengan:
- Autentikasi login admin
- Upload dokumen asli baru ke database
- Hapus dokumen dari database
- Daftar seluruh dokumen yang tersimpan

### 5. UI/UX Premium

- **Dark Glassmorphism Theme** dengan efek _backdrop-blur_ dan _gradient_
- **Particle Background** interaktif dengan efek:
  - _Antigravity_ (partikel menghindar dari kursor)
  - _Constellation_ (garis penghubung antar partikel)
  - _Mouse Glow Aura_ (pendaran cahaya di sekitar kursor)
- **Dark/Light Mode Toggle** dengan persistensi `localStorage`
- **Responsive Design** untuk desktop dan mobile

### 6. Bulk Import CLI

Management command `import_doksli` untuk mengimpor banyak gambar sekaligus dari direktori ke database, lengkap dengan:
- Ekstraksi embedding otomatis
- Deduplikasi via SHA-256 hash
- Laporan ringkasan (Success / Skipped / Errors / Total)

---

## Struktur Proyek

```
Capstone Project/
├── README.md
├── screenshot.png
├── .gitignore
│
├── backend/                          # Django Backend
│   ├── manage.py                     # Django CLI entry point
│   ├── requirements.txt              # Python dependencies
│   ├── .env                          # Environment variables (tidak di-track Git)
│   │
│   ├── config/                       # Django project settings
│   │   ├── settings.py               # Konfigurasi utama (DB, apps, middleware)
│   │   ├── urls.py                   # Root URL routing
│   │   └── wsgi.py / asgi.py
│   │
│   ├── api/                          # Django app utama
│   │   ├── models.py                 # 5 model database (UUID PK)
│   │   ├── serializers.py            # DRF serializers
│   │   ├── views.py                  # API views (search, admin, privacy)
│   │   ├── urls.py                   # API URL routing
│   │   ├── admin.py                  # Django admin registration
│   │   └── management/
│   │       └── commands/
│   │           └── import_doksli.py  # Bulk import CLI command
│   │
│   ├── services/                     # Business logic layer
│   │   ├── privacy_service.py        # Filter privasi (wajah, nama, alamat, dll.)
│   │   ├── embedding_service.py      # CNN feature extraction (MobileNetV2)
│   │   ├── similarity_service.py     # Cosine similarity comparison
│   │   ├── vision_service.py         # Google Cloud Vision API wrapper
│   │   └── cropping_service.py       # Image preprocessing & cropping
│   │
│   └── media/                        # File upload storage (tidak di-track Git)
│       ├── originals/                # Dokumen asli (Doksli)
│       └── queries/                  # Gambar query dari user
│
└── frontend/                         # React Frontend
    ├── package.json                  # Node.js dependencies
    ├── vite.config.js                # Vite config (proxy ke Django)
    ├── tailwind.config.js            # Tailwind CSS customization
    ├── index.html                    # HTML entry point
    │
    └── src/
        ├── main.jsx                  # React entry point
        ├── App.jsx                   # Router & layout wrapper
        ├── index.css                 # Global styles & CSS variables
        │
        ├── api/
        │   └── client.js             # Axios HTTP client & API functions
        │
        ├── components/
        │   ├── Layout.jsx            # Main layout (navbar + footer + particles)
        │   ├── Navbar.jsx            # Navigation bar + dark mode toggle
        │   ├── ParticleBackground.jsx# Canvas particle animation
        │   ├── ImageUpload.jsx       # Drag & drop image uploader
        │   ├── PrivacyBadge.jsx      # Privacy analysis result badges
        │   ├── ResultCard.jsx        # Search result card (clickable)
        │   └── DocumentCard.jsx      # Original document card
        │
        └── pages/
            ├── SearchPage.jsx        # Halaman utama (upload & analisis)
            ├── ResultDetailPage.jsx  # Detail hasil + modal perbandingan
            ├── AdminPage.jsx         # Dashboard admin (CRUD dokumen)
            └── OriginalsPage.jsx     # Daftar dokumen asli
```

---

## Struktur Database

Sistem menggunakan **PostgreSQL** dengan 5 entitas utama yang saling terhubung. Seluruh tabel menggunakan **UUID** sebagai Primary Key.

```mermaid
erDiagram
    OriginalDocument ||--o{ DocumentLabel : has
    OriginalDocument ||--o{ SearchResult : matched_by
    SearchQuery ||--|| PrivacyAnalysis : has
    SearchQuery ||--o{ SearchResult : produces

    OriginalDocument {
        uuid id PK
        text image_path
        json embedding_vector
        varchar(128) file_hash UK
        datetime created_at
    }

    DocumentLabel {
        uuid id PK
        uuid document_id FK
        varchar(50) label_type
        varchar(255) label_value
        float confidence_score
    }

    SearchQuery {
        uuid id PK
        text query_image_path
        varchar(128) query_hash
        varchar(10) search_source
        datetime created_at
    }

    PrivacyAnalysis {
        uuid id PK
        uuid search_id FK
        bool face_detected
        bool name_detected
        bool age_detected
        bool address_detected
        bool phone_detected
        int total_flags
        bool is_blocked
        datetime analyzed_at
    }

    SearchResult {
        uuid id PK
        uuid search_id FK
        varchar(10) source_type
        uuid matched_document_id FK
        text external_url
        float similarity_score
        datetime created_at
    }
```

### Detail Tabel

| Tabel | Deskripsi | Relasi |
|-------|-----------|--------|
| `OriginalDocument` | Dokumen referensi asli (Doksli) dengan embedding vektor 1280-dimensi | → DocumentLabel (1:N), → SearchResult (1:N) |
| `DocumentLabel` | Label fitur gambar hasil analisis Vision API (teks, logo, objek) | ← OriginalDocument (N:1) |
| `SearchQuery` | Riwayat pencarian/upload gambar oleh pengguna | → PrivacyAnalysis (1:1), → SearchResult (1:N) |
| `PrivacyAnalysis` | Hasil pemindaian 5 kategori privasi per pencarian | ← SearchQuery (1:1) |
| `SearchResult` | Hasil kecocokan individual (lokal atau Google) | ← SearchQuery (N:1), → OriginalDocument (N:1, nullable) |

---

## Service Layer (Backend)

### 1. `privacy_service.py` — Filter Privasi
Modul inti yang menganalisis gambar untuk konten sensitif sebelum pemrosesan utama.

| Fungsi | Deskripsi |
|--------|-----------|
| `analyze_privacy()` | Entry point utama — menjalankan seluruh pipeline deteksi |
| `_local_detect_faces()` | Deteksi wajah via OpenCV Haar Cascade + Histogram Equalization |
| `_local_detect_text()` | Ekstraksi teks via EasyOCR (bahasa Indonesia & Inggris) |
| `_detect_name_in_text()` | Deteksi nama menggunakan indikator kata kunci (toleran _typo_ OCR) |
| `_detect_age_in_text()` | Deteksi umur via regex pola `XX tahun` dan format TTL |
| `_detect_address_in_text()` | Deteksi alamat dengan _word-boundary_ berlapis (strict + loose) |
| `_detect_phone_in_text()` | Deteksi nomor telepon lokal (08x) dan internasional (+XX) |
| `_detect_nik_in_text()` | Deteksi NIK/No. Identitas (16-digit agresif) |

**Regex Patterns:**
```python
# NIK — Sangat resilien terhadap spasi dan kesalahan OCR
NIK_PATTERN = r'\b\d[\d\sO]{14,20}\b'

# Telepon — Format lokal Indonesia & internasional
PHONE_PATTERN = r'(\+\d{1,4}[\s\-]?(?:\d[\s\-]?){7,14}|08[\s\-]?(?:\d[\s\-]?){7,12})'

# Umur — Pola numerik + kata kunci
AGE_PATTERN = r'\b(\d{1,3})\s*(?:tahun|thn|th)\b'

# TTL — Tempat Tanggal Lahir
TTL_PATTERN = r'(?:tempat|tgl|tanggal|lahir).{0,30}?\d{1,2}[\s\-/. ,]+\d{1,2}[\s\-/. ,]+\d{2,4}'
```

### 2. `embedding_service.py` — Ekstraksi Fitur CNN
Menggunakan **MobileNetV2** (pre-trained ImageNet) sebagai _feature extractor_.

| Spesifikasi | Detail |
|-------------|--------|
| Model | MobileNetV2 (tanpa classifier) |
| Input | 224×224 RGB, ImageNet normalization |
| Output | Vektor 1280-dimensi, L2-normalized |
| Device | Auto-detect CUDA GPU → fallback CPU |
| Mode | Singleton loading, `torch.no_grad()` inference |

### 3. `similarity_service.py` — Perbandingan Kemiripan
Membandingkan embedding query terhadap seluruh dokumen asli menggunakan **Cosine Similarity**.

| Parameter | Nilai |
|-----------|-------|
| Threshold | 0.7 (minimum skor untuk dianggap cocok) |
| Metrik | Cosine Similarity (0.0 – 1.0) |
| Sorting | Descending berdasarkan skor kecocokan |

### 4. `vision_service.py` — Google Cloud Vision API
Wrapper untuk 3 fitur utama Google Cloud Vision:

| Fitur | Fungsi | Fallback |
|-------|--------|----------|
| **Face Detection** | Deteksi wajah dalam gambar | OpenCV Haar Cascade |
| **Text Detection (OCR)** | Ekstraksi teks dari gambar | EasyOCR |
| **Web Detection** | Pencarian gambar serupa di web | — |

**Autentikasi:**
1. Service Account JSON (`GOOGLE_APPLICATION_CREDENTIALS`) — prioritas utama
2. REST API + API Key (`GOOGLE_CLOUD_API_KEY`) — fallback

### 5. `cropping_service.py` — Preprocessing Gambar
Menyediakan fungsi cropping dan resize gambar sebelum diproses oleh model ML.

---

## Komponen Frontend

### Pages

| Halaman | Route | Deskripsi |
|---------|-------|-----------|
| `SearchPage` | `/` | Halaman utama — upload gambar, analisis privasi, mulai pencarian |
| `ResultDetailPage` | `/results/:searchId` | Detail hasil pencarian + modal perbandingan side-by-side |
| `AdminPage` | `/admin` | Dashboard admin (login, upload dokumen, hapus) |
| `OriginalsPage` | `/originals` | Daftar seluruh dokumen asli yang tersimpan |

### Components

| Komponen | Fungsi |
|----------|--------|
| `Layout` | Wrapper utama (Navbar + ParticleBackground + Footer) |
| `Navbar` | Navigasi + toggle Dark/Light mode |
| `ParticleBackground` | Efek partikel canvas interaktif (antigravity, constellation, glow) |
| `ImageUpload` | Komponen drag-and-drop upload gambar |
| `PrivacyBadge` | Menampilkan hasil analisis privasi (5 kategori flag) |
| `ResultCard` | Kartu hasil kecocokan (klikable untuk membuka modal perbandingan) |
| `DocumentCard` | Kartu dokumen asli di halaman admin/originals |

---

## API Endpoints

### Public Endpoints

| Method | Endpoint | Deskripsi | Request |
|--------|----------|-----------|---------|
| `POST` | `/api/search/` | Upload gambar untuk analisis privasi + pencarian kemiripan | `multipart/form-data` (`image`) |
| `GET` | `/api/results/<uuid>/` | Detail hasil pencarian berdasarkan ID | — |
| `GET` | `/api/originals/` | Daftar dokumen asli (paginated) | `?page=1` |

### Admin Endpoints

| Method | Endpoint | Deskripsi | Auth |
|--------|----------|-----------|------|
| `POST` | `/api/admin/login/` | Login admin | `{ username, password }` |
| `POST` | `/api/add-original/` | Upload dokumen asli baru | `multipart/form-data` (`image`) |
| `DELETE` | `/api/admin/originals/<uuid>/` | Hapus dokumen asli | Header `X-Admin-Auth` |

---

## Instalasi & Menjalankan Proyek

### Prasyarat

- **Python** 3.10+
- **Node.js** 18+ & npm
- **PostgreSQL** 15+ (atau SQLite untuk development cepat)
- **Git**

### 1. Clone Repository

```bash
git clone https://github.com/mezuuu/Aplikasi-Pencari-Doksli.git
cd Aplikasi-Pencari-Doksli
```

### 2. Setup Backend

```bash
cd backend

# Buat virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Konfigurasi environment
cp .env.example .env
# Edit .env sesuai kebutuhan (lihat bagian Environment Variables)

# Migrasi database
python manage.py migrate

# Buat akun admin (opsional)
python manage.py createsuperuser

# Jalankan server
python manage.py runserver
```

### 3. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Jalankan development server
npm run dev
```

### 4. Akses Aplikasi

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000/api/ |
| Django Admin | http://localhost:8000/admin/ |

> **Catatan:** Vite dev server secara otomatis mem-proxy request `/api` dan `/media` ke Django backend di port 8000.

---

## Environment Variables

Buat file `.env` di direktori `backend/` dengan konfigurasi berikut:

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True

# Database (PostgreSQL)
DATABASE_URL=postgres://username:password@localhost:5432/doksli_db

# Google Cloud Vision API
GOOGLE_CLOUD_API_KEY=your-api-key-here
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Privacy Filter
PRIVACY_FLAG_THRESHOLD=3
```

---

## Management Commands

### Bulk Import Dokumen Asli

```bash
python manage.py import_doksli "D:\path\to\image\directory"
```

**Fitur:**
- Memindai seluruh direktori secara rekursif
- Mendukung format: `.jpg`, `.jpeg`, `.png`, `.webp`
- Deduplikasi otomatis via SHA-256 hash
- Ekstraksi embedding CNN otomatis untuk setiap gambar
- Laporan ringkasan:

```
Bulk import completed!
Success: 10
Skipped: 205
Errors : 0
Total  : 215
```

---

## Lisensi

Proyek ini dikembangkan sebagai bagian dari tugas **Capstone Project**.

---

> _Seluruh sistem ini dirancang untuk berjalan otomatis pada environment CPU maupun GPU tanpa memerlukan fine-tuning atau pelatihan model (pre-trained inference only)._
