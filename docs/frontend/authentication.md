# Authentication

Secara bawaan (*default*), sistem obrolan ini didesain sebagai *widget* publik yang dapat diakses pengunjung situs tanpa perlu proses masuk (*login*). Namun, sistem ini memiliki tingkat pengamanan yang menyesuaikan dengan peran pengguna.

## 1. Akses Pelanggan Publik (Customer Widget)

Pelanggan *e-commerce* tidak perlu melampirkan JWT atau *header Authorization* saat terhubung ke WebSocket. 
Pelacakan sesi pelanggan dilakukan murni berdasarkan `conversation_id` berupa UUIDv4 yang dibangkitkan oleh pihak *Frontend* (Klien).

**Contoh Koneksi WebSocket Klien:**
```javascript
const conversationId = crypto.randomUUID();
// Cukup sematkan ID percakapan di URL
const ws = new WebSocket(`ws://localhost/api/v1/chat/ws/${conversationId}`);
```

> [!WARNING]
> Karena sifatnya yang anonim, jangan pernah memberikan instruksi kepada AI untuk membocorkan pesanan pelanggan secara spesifik tanpa melalui validasi email pelanggan (AI akan memintanya secara interaktif).

## 2. Akses Dashboard (Human Agent / Admin)

API yang berada di bawah lingkup Dasbor (seperti `analytics` dan `knowledge base`) diasumsikan diamankan menggunakan sistem eksternal atau proksi, karena repositori ini bertindak murni sebagai API.

Namun, untuk koneksi WebSocket Dasbor agar bisa memata-matai atau berinteraksi dalam obrolan pelanggan, *Frontend Admin* harus menyematkan token identifikasi dalam *header* (atau lewat *query param* tergantung konfigurasi Nginx/CORS).

**Saat ini, validasi otentikasi diimplementasikan di Nginx, sehingga Backend menerima semua *request* yang berhasil menembus Nginx.**
