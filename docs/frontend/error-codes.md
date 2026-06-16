# Error Codes

Panduan bagi pengembang *Frontend* untuk merespons kode galat yang dilempar oleh peladen API maupun *WebSocket*.

## 1. REST API Error Codes (HTTP)

Respons galat HTTP akan selalu memiliki struktur JSON:
```json
{
  "detail": "Penjelasan spesifik mengenai galat."
}
```

| Kode HTTP | Nama Error | Keterangan & Penanganan di Klien |
| :--- | :--- | :--- |
| `400` | Bad Request | Parameter kueri atau badan permintaan JSON cacat. Klien perlu memperbaiki format data yang dikirim. |
| `401` | Unauthorized | Autentikasi dasbor gagal, atau sesi sudah kedaluwarsa. |
| `404` | Not Found | Sumber daya (contoh: *Conversation ID*) tidak ada di dalam *database*. |
| `422` | Unprocessable Entity | Pydantic menolak validasi tipe data (contoh: `limit` bukan angka). |
| `429` | Too Many Requests | *Rate limiting* tersentuh. Klien harap melambat. |
| `500` | Internal Server Error | Kesalahan fatal (*Database Down*, dll). Hubungi Admin. |
| `503` | Service Unavailable | *Worker Queue* mati atau kelebihan beban antrean. |

---

## 2. WebSocket Close Codes (WSS)

Koneksi *WebSocket* tidak melempar kode HTTP saat terputus secara sepihak, melainkan melempar *Closure Code* standar spesifikasi WebSockets.

| Closure Code | Alasan (*Reason*) | Tindakan *Frontend* |
| :--- | :--- | :--- |
| `1000` | Normal Closure | Sesi diakhiri secara wajar (pengguna keluar). Tidak perlu melakukan *reconnect*. |
| `1006` | Abnormal Closure | Koneksi internet pelanggan putus tiba-tiba atau *container* mati secara kasar. Lakukan sambung ulang otomatis (*auto-reconnect*). |
| `1008` | Policy Violation | Pesan yang dikirim terlalu besar. Batasi teks *input*. |
| `1011` | Internal Error | Server kehabisan kapasitas memori atau batas tunggu sambungan Redis (*Timeout*). Tunggu 5-10 detik sebelum mencoba *reconnect* karena server butuh waktu *recovery*. |
