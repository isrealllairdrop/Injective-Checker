# 💸 Injective EVM Wallet Manager Bot

Skrip Python otomatis untuk **memantau, mengumpulkan, dan menyebarkan token** (INJ, USDT, wINJ) di jaringan **Injective EVM Testnet**. Cocok untuk testnet farming, simulasi batch transfer, atau manajemen banyak wallet ("tuyul").

---

## 🚀 Fitur Utama

- ✅ **Cek saldo semua wallet (utama & tuyul)**
- 🔁 **Kumpulkan semua token dari wallet tuyul ke wallet utama**
- 🎯 **Sebar token dari wallet utama ke semua wallet tuyul**
- 🌐 **Mendukung penggunaan proxy**
- 🔄 **Retry otomatis saat jaringan error**
- ⚙️ **Konfigurasi token bisa diatur dalam script**

---

## 📁 Struktur File

Letakkan file berikut di direktori yang sama dengan `bot.py`:

| File               | Deskripsi                                      |
|--------------------|------------------------------------------------|
| `addressutama.txt` | Alamat wallet utama (1 baris)                 |
| `pvkeyutama.txt`   | Private key wallet utama (1 baris)            |
| `addresstuyul.txt` | Daftar alamat wallet tuyul (1 per baris)      |
| `pvkeytuyul.txt`   | Daftar private key tuyul (1 per baris)        |

---

## 🧪 Konfigurasi Jaringan

- **Jaringan**: Injective EVM Testnet  
- **RPC**: `https://k8s.testnet.json-rpc.injective.network/`  
- **Chain ID**: `1439`  
- **Explorer**: [Blockscout Testnet](https://testnet.blockscout.injective.network/)

---

## ▶️ Menjalankan

### 1. Instal dependensi:
```bash
pip install web3 colorama
```

### 2. Jalankan bot:
```bash
python bot.py
```

---

## 📞 Kontak & Dukungan
Punya pertanyaan, kritik, atau saran? Jangan ragu untuk menghubungi saya.

- Telegram: https://t.me/Isrealll1
- Website: https://isrealllairdrop.tech/
