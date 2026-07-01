# Panduan Deployment Dokploy: Pendekatan "Application" & "Database" Terpisah

Panduan ini akan memandu Anda untuk men-deploy aplikasi Customer Service AI (Backend, Worker, Frontend, dan Ollama) di Dokploy. Pendekatan ini (memisahkan aplikasi dan database) sangat direkomendasikan untuk skalabilitas dan manajemen yang lebih rapi dibandingkan menggunakan *Docker Compose*.

---

## 1. Setup Database & Redis
Hal pertama yang harus disiapkan adalah wadah datanya.
1. Di Dashboard Dokploy, masuk ke menu **Project > Environment**.
2. Klik **Create Service** > Pilih **Database** > Pilih **PostgreSQL** (Gunakan versi 16).
3. Klik **Create Service** > Pilih **Database** > Pilih **Redis**.
4. Setelah keduanya selesai dibuat, catat **Internal Connection String** dari masing-masing database. Formatnya kira-kira seperti ini:
   - PostgreSQL: `postgresql://user:pass@postgres-1234:5432/dbname`
   - Redis: `redis://default:pass@redis-1234:6379/0`
   > **Catatan:** Untuk PostgreSQL di Python, Anda harus mengubah prefix `postgresql://` menjadi `postgresql+asyncpg://`.

---

## 2. Setup Backend (API Utama)
1. Klik **Create Service** > Pilih **Application**.
2. Beri nama: `api` (atau `cs-ai-api`).
3. Pada tab **General**:
   - Provider: **Github**
   - Repository: `backend-csai-template`
   - Build Type: **Dockerfile** (biarkan path-nya di `Dockerfile`).
4. Pada tab **Environment**, masukkan konfigurasi `.env` Anda, terutama:
   ```env
   DATABASE_URL=postgresql+asyncpg://[KONEKSI_INTERNAL_DOKPLOY]
   REDIS_URL=redis://[KONEKSI_INTERNAL_DOKPLOY]
   JWT_SECRET_KEY=string_acak_rahasia_anda_minimal_32_karakter
   ```
5. Pada tab **Ports**, masukkan `8000`.
6. Pada tab **Domains**, tambahkan domain Anda (misal `api.domain.com`) dan arahkan ke port `8000`.
7. Klik **Deploy**.

---

## 3. Setup Worker (Antrean Latar Belakang)
Worker menggunakan kode yang persis sama dengan API, tapi dengan *start command* yang berbeda.
1. Klik **Create Service** > Pilih **Application**.
2. Beri nama: `worker`.
3. Pada tab **General**:
   - Provider: **Github**
   - Repository: `backend-csai-template` (Repo yang sama dengan API).
   - Build Type: **Dockerfile**.
   - **Docker File**: Ubah dari `Dockerfile` menjadi **`worker.Dockerfile`**.
4. Pada tab **Environment**, **samakan isinya 100%** dengan tab Environment di aplikasi `API`. (Pastikan `REDIS_URL` dan `DATABASE_URL`-nya persis).
5. Tidak perlu mengisi Domains atau Ports.
6. Klik **Deploy**.

---

## 4. Setup Frontend
1. Klik **Create Service** > Pilih **Application**.
2. Beri nama: `frontend`.
3. Pada tab **General**:
   - Provider: **Github**
   - Repository: Repo Frontend Anda.
   - Build Type: **Dockerfile**.
4. Pada tab **Environment**, masukkan konfigurasi yang diperlukan React/Vite:
   ```env
   VITE_API_URL=https://api.domain.com
   ```
5. Pada tab **Ports**, masukkan **`3000`** *(karena `serve` di Dockerfile frontend berjalan di port 3000).*
6. Pada tab **Domains**, tambahkan domain (misal `app.domain.com`) dan arahkan ke Port **`3000`** *(Bukan 8080)*.
7. Klik **Deploy**.

---

## 5. Setup Ollama (AI Model Lokal)
Jika Anda menggunakan model lokal (LLaMA3, Gemma), ini cara men-deploy-nya agar terpisah:
1. Klik **Create Service** > Pilih **Application**.
2. Beri nama: `ollama`.
3. Pada tab **General**:
   - Source: Ubah dari Github menjadi **Docker Image**.
   - Image: `ollama/ollama:latest`
4. Pada tab **Advanced / Volumes** (Sangat Penting):
   - Tambahkan *Volume*.
   - Host path (atau nama volume): `ollama_data`
   - Container path: `/root/.ollama`
5. Pada tab **Ports**, isi `11434`. Tidak perlu diberi domain publik agar aman.
6. Klik **Deploy**.
7. Setelah berjalan, buka tab **Terminal/Exec** di Dokploy pada service `ollama` ini, lalu ketikkan:
   ```bash
   ollama pull llama3
   ```
8. **Hubungkan ke API & Worker:** Buka konfigurasi Environment `API` dan `Worker`, lalu tambahkan:
   ```env
   OLLAMA_BASE_URL=http://ollama:11434
   ```
   (Klik Deploy/Restart API & Worker setelah mengubah Env ini).

---

## 6. Langkah Final (Post-Deployment)
Database yang baru Anda buat masih kosong. Anda harus membentuk struktur tabel dan membuat akun Super Admin pertama.

1. Buka service **API** di Dokploy.
2. Buka tab **Terminal** (atau *Exec*) untuk masuk ke dalam *container* API yang sedang berjalan.
3. **Lakukan Migrasi Database (Bikin Tabel):**
   Ketik perintah berikut lalu tekan Enter:
   ```bash
   alembic upgrade head
   ```
4. **Buat Default User (Super Admin):**
   Ketik perintah berikut lalu tekan Enter:
   ```bash
   python scripts/create_default_user.py
   ```
   *Secara bawaan, script ini akan membuatkan akun dengan email `admin@admin.com` dan password `admin123`. Anda bisa login ke Frontend dengan kredensial tersebut, lalu segera ubah passwordnya demi keamanan!*

🎉 **Selesai! Sistem Customer Service AI Anda sudah sepenuhnya berjalan di Awam!**
