# Pagination

API dalam *Customer Service AI Backend* menggunakan standar paginasi berbasis kursor dan parameter *offset-limit* klasik tergantung pada jenis data yang dikembalikan.

## 1. Parameter Kueri (Query Parameters)

Sebagian besar *endpoint* REST API yang mengembalikan daftar/koleksi (seperti daftar tiket atau daftar riwayat obrolan di Dasbor) mendukung kueri berikut:

| Parameter | Tipe | Default | Maksimum | Deskripsi |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | *Integer* | 20 | 100 | Jumlah maksimal objek yang dikembalikan dalam satu balasan. |
| `offset` | *Integer* | 0 | N/A | Jumlah objek yang dilewati (*skipped*) sejak indeks ke-0. |

**Contoh URL:**
`GET /api/v1/conversations?limit=50&offset=100`

---

## 2. Struktur Respons Paginasi

Data respons tidak langsung mengembalikan *array*, melainkan dibungkus dengan meta informasi tambahan agar klien bisa merender tombol *"Halaman Selanjutnya"*.

```json
{
  "data": [
    {
      "id": "item_1",
      "name": "Data 1"
    },
    {
      "id": "item_2",
      "name": "Data 2"
    }
  ],
  "meta": {
    "total_items": 150,
    "limit": 50,
    "offset": 100,
    "has_next": true,
    "has_previous": true
  }
}
```

### Panduan Implementasi Frontend
- Tombol **"Selanjutnya"**: Tambahkan nilai `limit` pada parameter `offset`. (Misal: dari `offset=100` menjadi `offset=150`).
- Sembunyikan tombol *"Selanjutnya"* jika `has_next` merespons `false`.
