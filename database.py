import sqlite3


def create_tables():
    conn = sqlite3.connect("nft_auth.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS username (id INTEGER PRIMARY KEY, telegramID text, tonWallet text)")
    # payment table
    cur.execute("CREATE TABLE IF NOT EXISTS payment (id INTEGER PRIMARY KEY, telegramID text, tonWallet text, amount text, date text)")
    conn.commit()
    conn.close()

def insert(telegramID, tonWallet):
    conn = sqlite3.connect("nft_auth.db")
    cur = conn.cursor()
    # remove old wallet
    cur.execute("DELETE FROM username WHERE telegramID=?", (telegramID,))
    cur.execute("INSERT INTO username VALUES (NULL, ?, ?)", (telegramID, tonWallet))
    conn.commit()
    conn.close()

def insert_payment(telegramID, tonWallet, amount, date):
    conn = sqlite3.connect("nft_auth.db")
    cur = conn.cursor()
    cur.execute("INSERT INTO payment VALUES (NULL, ?, ?, ?, ?)", (telegramID, tonWallet, amount, date))
    conn.commit()
    conn.close()

def view():
    conn = sqlite3.connect("nft_auth.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM username")
    rows = cur.fetchall()
    conn.close()
    return rows

def search(telegramID="", tonWallet=""):
    conn = sqlite3.connect("nft_auth.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM username WHERE telegramID=? OR tonWallet=?", (telegramID, tonWallet))
    rows = cur.fetchall()
    conn.close()
    return rows

def check_payment_existence(telegramID, tonWallet):
    conn = sqlite3.connect("nft_auth.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM payment WHERE telegramID=? AND tonWallet=?", (telegramID, tonWallet))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_wallet_by_telegram_id(telegramID):
    conn = sqlite3.connect("nft_auth.db")
    cur = conn.cursor()
    cur.execute("SELECT tonWallet FROM username WHERE telegramID=?", (telegramID,))
    rows = cur.fetchall()
    conn.close()
    return rows