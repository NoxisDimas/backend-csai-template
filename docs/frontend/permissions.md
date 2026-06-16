# Permissions & Roles

Dokumen ini mendeskripsikan lingkup otoritas yang dimiliki oleh setiap peran dalam sistem.

## 1. Peran Sistem

Ada 3 entitas atau peran utama dalam kerangka kerja ini:
1. **Customer (Pelanggan)**: Pengunjung situs web Shopify.
2. **AI Agent (Bot)**: Orkestrator LangGraph yang menangani obrolan awal.
3. **Human Agent (Agen/Admin)**: Staf CS manusia yang melakukan intervensi obrolan via Dasbor.

---

## 2. Tabel Matriks Akses (Access Control)

| Aksi / Fungsi | Customer | AI Agent | Human Agent |
| :--- | :---: | :---: | :---: |
| Mengirim Pesan Chat | ✅ | ✅ | ✅ |
| Melihat History Obrolan | ✅ (Hanya Sesi Sendiri) | ✅ | ✅ (Semua) |
| Melihat Rangkuman Dasbor | ❌ | ❌ | ✅ |
| Melakukan Unggah FAQ/Doc | ❌ | ❌ | ✅ |
| Mencari Produk/Stok | ✅ (Secara Tidak Langsung via AI) | ✅ (Akses GraphQL Penuh) | ✅ (Dashboard) |
| Eskalasi (Minta Bantuan) | ✅ | ✅ (Pemicu) | ❌ |
| Intervensi / Handoff | ❌ | ❌ | ✅ |

> [!CAUTION]
> *Human Agent* memiliki akses baca (`Read`) ke semua percakapan yang masuk ke sistem. Oleh karena itu, *Customer* **TIDAK BOLEH** mengirimkan PIN atau kata sandi melalui saluran obrolan.
