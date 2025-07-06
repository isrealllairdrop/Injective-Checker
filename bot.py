import os
import sys
import time
import json
from functools import wraps
from web3 import Web3
from web3.exceptions import TransactionNotFound
from colorama import init, Fore, Style

# Inisialisasi Colorama
init(autoreset=True)

# ========================================================================================
# --- Definisi Warna ---
# ========================================================================================
C_SUCCESS = Fore.GREEN
C_ERROR = Fore.RED
C_WARN = Fore.YELLOW
C_INFO = Fore.BLUE
C_HEADER = Fore.CYAN
C_RESET = Style.RESET_ALL

# ========================================================================================
# --- KONFIGURASI UTAMA ---
# ========================================================================================
NETWORK_NAME = "Injective EVM Testnet"
RPC_URL = "https://k8s.testnet.json-rpc.injective.network/"
CHAIN_ID = 1439
EXPLORER_URL = "https://testnet.blockscout.injective.network/tx/"
NATIVE_CURRENCY = "INJ"
GAS_LIMIT_NATIVE = 21000
GAS_LIMIT_ERC20 = 75000
USDT_CONFIG = {"address": Web3.to_checksum_address("0xaDC7bcB5d8fe053Ef19b4E0C861c262Af6e0db60"), "symbol": "USDT", "decimals": 6}
WINJ_CONFIG = {"address": Web3.to_checksum_address("0x0000000088827d2d103ee2d9A6b781773AE03FfB"), "symbol": "wINJ", "decimals": 18}
MINIMAL_ERC20_ABI = json.loads('[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}, {"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}]')


# ========================================================================================
# --- PENGATURAN FITUR 'KUMPULKAN DANA' (GATHER) ---
# ========================================================================================
# Ubah nilai di bawah ini menjadi False jika Anda TIDAK ingin mengumpulkan token tersebut.
KUMPULKAN_USDT = False
KUMPULKAN_WINJ = False
# Pengumpulan sisa INJ akan selalu dijalankan sebagai langkah terakhir.


# ========================================================================================
# --- DECORATOR UNTUK RETRY ---
# ========================================================================================
def retry_on_network_error(retries=3, delay=5, backoff=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            m_retries, m_delay = retries, delay
            while m_retries > 0:
                try: return func(*args, **kwargs)
                except Exception as e:
                    if any(err_msg in str(e) for err_msg in ["503", "502", "504", "Service Unavailable", "Connection timed out", "Connection broken"]):
                        m_retries -= 1
                        if m_retries > 0:
                            print(f"\n{C_ERROR}(!) Terjadi error jaringan. Mencoba lagi dalam {m_delay} detik...")
                            time.sleep(m_delay); m_delay *= backoff
                        else: raise Exception("GAGAL (Error Jaringan setelah beberapa kali percobaan)")
                    else: raise
            return None
        return wrapper
    return decorator

# ========================================================================================
# --- FUNGSI-FUNGSI BANTUAN ---
# ========================================================================================
def clear_screen(): os.system('cls' if os.name == 'nt' else 'clear')
def read_file_lines(filename):
    try:
        with open(filename, 'r') as f: return [line.strip() for line in f if line.strip()]
    except FileNotFoundError: print(f"{C_ERROR}(!) ERROR: File '{filename}' tidak ditemukan."); return []
def read_single_line_file(filename):
    lines = read_file_lines(filename); return lines[0] if lines else None
def setup_web3(use_proxy=False, proxy_url=None):
    print(f"{C_INFO}Menghubungkan ke RPC...")
    session_kwargs = {}
    if use_proxy and proxy_url:
        print(f"{C_INFO}--> Menggunakan proxy: {proxy_url}")
        session_kwargs = {"proxies": {"http": proxy_url, "https": proxy_url}}
    w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs=session_kwargs))
    if not w3.is_connected(): print(f"{C_ERROR}(!) GAGAL terhubung ke RPC."); return None
    print(f"{C_SUCCESS}--> Berhasil terhubung ke {NETWORK_NAME} (Chain ID: {w3.eth.chain_id})")
    return w3

# ========================================================================================
# --- FUNGSI INTI & HELPER ---
# ========================================================================================

@retry_on_network_error()
def _send_and_wait(w3, signed_tx):
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        return (f"{C_SUCCESS}BERHASIL", tx_hash.hex()) if receipt.status == 1 else (f"{C_ERROR}GAGAL (Status Reverted)", tx_hash.hex())
    except TransactionNotFound:
        return (f"{C_ERROR}GAGAL (Timeout)", tx_hash.hex())

def _send_native_token(w3, pk, to, send_all=False, amount_in_ether=None, nonce_val=None):
    print(f"{C_INFO}Mencoba mengirim {NATIVE_CURRENCY}: ", end="", flush=True)
    try:
        sender_address = w3.eth.account.from_key(pk).address
        to = Web3.to_checksum_address(to)
        nonce = nonce_val if nonce_val is not None else w3.eth.get_transaction_count(sender_address, 'pending')
        gas_price = w3.eth.gas_price
        
        if send_all:
            balance_wei = w3.eth.get_balance(sender_address)
            amount_to_send_wei = balance_wei - (gas_price * GAS_LIMIT_NATIVE)
            if amount_to_send_wei <= 0:
                print(f"{C_WARN}SALDO TIDAK CUKUP"); return False
        else:
            amount_to_send_wei = w3.to_wei(amount_in_ether, 'ether')

        tx_params = {'nonce': nonce, 'to': to, 'value': amount_to_send_wei, 'gas': GAS_LIMIT_NATIVE, 'gasPrice': gas_price, 'chainId': CHAIN_ID}
        signed_tx = w3.eth.account.sign_transaction(tx_params, pk)
        status, tx_hash = _send_and_wait(w3, signed_tx)
        print(status)
        if tx_hash:
            print(f"Tx Hash : {C_WARN}{tx_hash}")
            print(f"Lihat di Explorer : {EXPLORER_URL}{tx_hash}")
        return "BERHASIL" in status
    except Exception as e:
        print(f"{C_ERROR}GAGAL (Error: {e})"); return False

def _send_erc20_token(w3, pk, to, token_config, send_all=False, amount=None, nonce_val=None):
    symbol = token_config['symbol']
    print(f"{C_INFO}Mencoba mengirim {symbol}: ", end="", flush=True)
    try:
        sender_address = w3.eth.account.from_key(pk).address
        to = Web3.to_checksum_address(to)
        token_contract = w3.eth.contract(address=token_config['address'], abi=MINIMAL_ERC20_ABI)
        
        if send_all:
            balance_raw = token_contract.functions.balanceOf(sender_address).call()
            if balance_raw <= 0:
                print(f"{C_WARN}SALDO KOSONG"); return False
            amount_to_send_raw = balance_raw
        else:
            amount_to_send_raw = int(amount * (10**token_config['decimals']))

        nonce = nonce_val if nonce_val is not None else w3.eth.get_transaction_count(sender_address, 'pending')
        tx_params = token_contract.functions.transfer(to, amount_to_send_raw).build_transaction({
            'chainId': CHAIN_ID, 'from': sender_address, 'gas': GAS_LIMIT_ERC20,
            'gasPrice': w3.eth.gas_price, 'nonce': nonce
        })
        signed_tx = w3.eth.account.sign_transaction(tx_params, pk)
        status, tx_hash = _send_and_wait(w3, signed_tx)
        print(status)
        if tx_hash:
            print(f"Tx Hash : {C_WARN}{tx_hash}")
            print(f"Lihat di Explorer : {EXPLORER_URL}{tx_hash}")
        return "BERHASIL" in status
    except Exception as e:
        print(f"{C_ERROR}GAGAL (Error: {e})"); return False

@retry_on_network_error()
def _get_nonce_with_retry(w3, address):
    """Mengambil nonce untuk sebuah alamat dengan mekanisme retry."""
    return w3.eth.get_transaction_count(address, 'pending')
    
@retry_on_network_error()
def _display_balance_and_get_values(w3, address):
    checksum_address = Web3.to_checksum_address(address)
    print(f"Alamat: {C_WARN}{checksum_address}")
    balance_wei = w3.eth.get_balance(checksum_address)
    print(f"  - {NATIVE_CURRENCY}: {C_SUCCESS}{w3.from_wei(balance_wei, 'ether'):.8f}")
    winj_contract = w3.eth.contract(address=WINJ_CONFIG['address'], abi=MINIMAL_ERC20_ABI)
    winj_balance_raw = winj_contract.functions.balanceOf(checksum_address).call()
    print(f"  - {WINJ_CONFIG['symbol']}: {C_SUCCESS}{winj_balance_raw / (10**WINJ_CONFIG['decimals']):.8f}")
    usdt_contract = w3.eth.contract(address=USDT_CONFIG['address'], abi=MINIMAL_ERC20_ABI)
    usdt_balance_raw = usdt_contract.functions.balanceOf(checksum_address).call()
    print(f"  - {USDT_CONFIG['symbol']}: {C_SUCCESS}{usdt_balance_raw / (10**USDT_CONFIG['decimals']):.6f}")
    return balance_wei, winj_balance_raw, usdt_balance_raw

def check_all_balances():
    w3 = setup_web3();
    if not w3: return
    total_inj_wei, total_winj_raw, total_usdt_raw = 0, 0, 0
    main_address = read_single_line_file('addressutama.txt')
    if main_address:
        print(f"\n{C_HEADER}--- Memeriksa Saldo Wallet Utama ---")
        inj, winj, usdt = _display_balance_and_get_values(w3, main_address)
        total_inj_wei, total_winj_raw, total_usdt_raw = total_inj_wei+inj, total_winj_raw+winj, total_usdt_raw+usdt
    tuyul_addresses = read_file_lines('addresstuyul.txt')
    if tuyul_addresses:
        print(f"\n{C_HEADER}--- Memeriksa Saldo Wallet Tuyul ---")
        for i, address in enumerate(tuyul_addresses):
            print(f"\n{C_HEADER}--- Wallet Tuyul #{i+1} ---")
            inj, winj, usdt = _display_balance_and_get_values(w3, address)
            total_inj_wei, total_winj_raw, total_usdt_raw = total_inj_wei+inj, total_winj_raw+winj, total_usdt_raw+usdt
            if i < len(tuyul_addresses) - 1: time.sleep(1)
    print("\n" + C_HEADER + "="*50)
    print(C_HEADER + "---      TOTAL SALDO KESELURUHAN         ---")
    print(f"{C_HEADER}    Total {NATIVE_CURRENCY}: {C_SUCCESS}{w3.from_wei(total_inj_wei, 'ether'):.8f}")
    print(f"{C_HEADER}    Total {WINJ_CONFIG['symbol']}: {C_SUCCESS}{total_winj_raw / (10**WINJ_CONFIG['decimals']):.8f}")
    print(f"{C_HEADER}    Total {USDT_CONFIG['symbol']}: {C_SUCCESS}{total_usdt_raw / (10**USDT_CONFIG['decimals']):.6f}")
    print(C_HEADER + "="*50)

def gather_funds():
    """Menjalankan fitur Kumpulkan Dana dengan konfigurasi dari dalam skrip."""
    print(f"\n{C_HEADER}--- Mode: Kumpulkan Dana dari Tuyul ke Utama ---")
    main_address = read_single_line_file('addressutama.txt')
    if not main_address: print(f"{C_ERROR}(!) Alamat utama tidak ditemukan."); return
    main_address = Web3.to_checksum_address(main_address)
    
    print(f"{C_INFO}Pengaturan Pengumpulan Dana:")
    print(f"{C_INFO} - Kumpulkan {USDT_CONFIG['symbol']}: {'Ya' if KUMPULKAN_USDT else 'Tidak'}")
    print(f"{C_INFO} - Kumpulkan {WINJ_CONFIG['symbol']}: {'Ya' if KUMPULKAN_WINJ else 'Tidak'}")
    
    if input(f"{C_WARN}Lanjutkan dengan pengaturan di atas? (y/n): ").lower() != 'y':
        print("Operasi dibatalkan."); return

    use_proxy = input(f"{C_WARN}Gunakan proxy untuk operasi ini? (y/n): ").lower() == 'y'
    proxy_url = input("Masukkan URL proxy: ") if use_proxy else None
    w3 = setup_web3(use_proxy, proxy_url)
    if not w3: return

    tuyul_pks = read_file_lines('pvkeytuyul.txt')
    if not tuyul_pks: print(f"{C_ERROR}(!) Private key tuyul tidak ditemukan."); return

    for i, pk in enumerate(tuyul_pks):
        try:
            sender_address = w3.eth.account.from_key(pk).address
            print(f"\n{C_HEADER}===== Memproses Tuyul #{i+1}: {C_WARN}{sender_address} =====")
            
            if KUMPULKAN_USDT:
                _send_erc20_token(w3, pk, main_address, USDT_CONFIG, send_all=True)
            if KUMPULKAN_WINJ:
                _send_erc20_token(w3, pk, main_address, WINJ_CONFIG, send_all=True)
            
            _send_native_token(w3, pk, main_address, send_all=True)

        except Exception as e:
            print(f"{C_ERROR}(!) Gagal memproses wallet #{i+1} karena private key tidak valid atau error lain: {e}")
        
        if i < len(tuyul_pks) - 1:
            print(f"{C_INFO}--> Menunggu 5 detik...")
            time.sleep(5)

def distribute_funds():
    # ... (Fungsi ini tidak diubah dari versi sebelumnya)
    w3 = setup_web3()
    if not w3: return
    print(f"\n{C_HEADER}--- Mode: Sebar Dana dari Utama ke Tuyul ---")
    main_pk = read_single_line_file('pvkeyutama.txt')
    if not main_pk: print(f"{C_ERROR}(!) Private key utama tidak ditemukan."); return
    tuyul_addresses = read_file_lines('addresstuyul.txt')
    if not tuyul_addresses: print(f"{C_ERROR}(!) Tidak ada alamat tuyul."); return
    try:
        sender_address = w3.eth.account.from_key(main_pk).address
        print(f"Wallet utama terdeteksi: {C_WARN}{sender_address}")
    except Exception: print(f"{C_ERROR}(!) Private key utama tidak valid!"); return
    print(f"\n{C_INFO}--> Silakan masukkan jumlah token yang akan disebar ke setiap wallet.")
    print(f"{C_INFO}--> Tekan ENTER (kosongkan) jika tidak ingin menyebar token tersebut.")
    amount_inj_str = input(f"Jumlah {NATIVE_CURRENCY} untuk disebar: ")
    amount_winj_str = input(f"Jumlah {WINJ_CONFIG['symbol']} untuk disebar: ")
    amount_usdt_str = input(f"Jumlah {USDT_CONFIG['symbol']} untuk disebar: ")
    try:
        amount_inj = float(amount_inj_str) if amount_inj_str else 0
        amount_winj = float(amount_winj_str) if amount_winj_str else 0
        amount_usdt = float(amount_usdt_str) if amount_usdt_str else 0
    except ValueError: print(f"{C_ERROR}(!) Input jumlah tidak valid. Operasi dibatalkan."); return
    if not any([amount_inj > 0, amount_winj > 0, amount_usdt > 0]): print("Tidak ada jumlah yang dimasukkan. Operasi dibatalkan."); return
    print(f"\n{C_INFO}Memulai proses penyebaran dana...")
    current_nonce = _get_nonce_with_retry(w3, sender_address)
    if current_nonce is None: return
    for i, address in enumerate(tuyul_addresses):
        print(f"\n{C_HEADER}--- Mengirim ke Tuyul #{i+1}: {C_WARN}{address} ---")
        if amount_inj > 0:
            if _send_native_token(w3, main_pk, address, amount_in_ether=amount_inj, nonce_val=current_nonce):
                current_nonce += 1
        if amount_winj > 0:
            if _send_erc20_token(w3, main_pk, address, WINJ_CONFIG, amount=amount_winj, nonce_val=current_nonce):
                current_nonce += 1
        if amount_usdt > 0:
            if _send_erc20_token(w3, main_pk, address, USDT_CONFIG, amount=amount_usdt, nonce_val=current_nonce):
                current_nonce += 1
        if i < len(tuyul_addresses) - 1: print(f"{C_INFO}--> Menunggu 10 detik..."); time.sleep(10)

def main():
    """Fungsi utama yang menjalankan loop menu."""
    clear_screen()
    print(C_HEADER + "="*65)
    print(C_HEADER + "=== INJECTIVE EVM CEKSEND BOT ===")
    print(C_HEADER + "="*65)
    while True:
        print(f"\n{C_HEADER}MENU UTAMA:")
        print("  1. Cek Saldo Semua Akun (dengan Total)")
        print("  2. Kumpulkan Dana dari Tuyul ke Utama (Gather)")
        print("  3. Sebar Dana Multi-Token dari Utama ke Tuyul (Distribute)")
        print("  4. Keluar")
        choice = input(f"{C_WARN}Masukkan pilihan Anda (1-4): ")
        if choice == '1': check_all_balances()
        elif choice == '2': gather_funds()
        elif choice == '3': distribute_funds()
        elif choice == '4': print("\nTerima kasih!"); break
        else: print(f"{C_ERROR}(!) Pilihan tidak valid.")
        input(f"\n{C_WARN}Tekan ENTER untuk kembali ke menu utama...")
        clear_screen()
        print(C_HEADER + "="*65)
        print(C_HEADER + "===   SELAMAT DATANG DI INJECTIVE EVM BOT v8.1 (CONFIGURABLE)   ===")
        print(C_HEADER + "="*65)

if __name__ == "__main__":
    main()
