# WebSocket Events

Saluran komunikasi utama antara aplikasi *Frontend* pelanggan dengan *AI Backend* terjadi melalui koneksi WebSocket *full-duplex*.

## 1. Membuka Koneksi

```javascript
// URL koneksi
const ws = new WebSocket('ws://<domain>/api/v1/chat/ws/<conversation_id>');
```
Ketika berhasil tersambung, klien akan langsung terdaftar di *Redis Pub/Sub* sehingga semua *node* API bisa berkomunikasi dengannya.

---

## 2. Format Pesan Masuk (Client -> Server)

Pelanggan atau agen manusia mengirim pesan dalam format JSON:

```json
{
  "type": "message",
  "text": "Apakah sepatu Nike Air ukuran 42 tersedia?",
  "sender": "customer" 
}
```

> [!NOTE]
> Parameter `sender` membedakan apakah pesan ini berasal dari pelanggan anonim (`"customer"`) atau dari staf *Customer Service* manusia yang melakukan intervensi obrolan (`"human_agent"`).

---

## 3. Format Pesan Keluar (Server -> Client)

Sistem akan membalas pesan dalam beberapa tipe format (`type`), agar *Frontend* bisa merender UI yang sesuai (misal: memunculkan indikator mengetik).

### A. Indikator Mengetik
Dikirimkan beberapa milidetik setelah pelanggan mengirim pertanyaan, menandakan bahwa AI sedang berpikir.
```json
{
  "type": "typing",
  "status": true
}
```

### B. Balasan Teks AI & Rekomendasi Produk
Pesan akhir dari AI. Menandakan bahwa AI sudah selesai meracik jawaban. Respons ini juga menyertakan struktur data produk untuk mempermudah Frontend merender UI (seperti Product Card) jika AI merekomendasikan barang tertentu.
```json
{
  "type": "new_message",
  "sender": "ai",
  "messages": "Halo! Sepatu Nike Air ukuran 42 kebetulan masih tersedia 2 stok lagi di gudang utama kami.",
  "has_product": true,
  "products": [
    {
      "title": "Nike Air",
      "url": "https://store.com/products/nike-air",
      "image_url": "https://store.com/cdn/nike-air.jpg",
      "price": "Rp 1.200.000"
    }
  ]
}
```

### C. Mode Eskalasi (Handoff)
Ketika AI mendeteksi pelanggan frustrasi atau sistem gagal menangani keluhan, AI akan mengirimkan peringatan khusus ke antarmuka klien. *Frontend* dapat merender peringatan *"Menghubungkan ke agen manusia..."*.
```json
{
  "type": "escalation",
  "status": "triggered",
  "message": "Mohon tunggu sebentar, kami sedang menghubungkan Anda ke Agen kami yang dapat membantu Anda lebih lanjut."
}
```
