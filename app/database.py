import os
import sqlite3
import base64
from datetime import datetime
from cryptography.fernet import Fernet
import hashlib

DB_PATH = "/data/routers.db"

def get_encryption_key() -> bytes:
    """
    Get or derive a valid 32-byte URL-safe base64 key for Fernet.
    If DATA_ENCRYPTION_KEY is not defined, we use a default secret.
    If a key is provided but is not exactly a valid Fernet key format,
    we derive a secure 32-byte key from it using PBKDF2.
    """
    key = os.getenv("DATA_ENCRYPTION_KEY", "default-mikrotik-dashboard-stable-secret-key")
    
    # Check if the key is already a valid Fernet key
    try:
        decoded = base64.urlsafe_b64decode(key.encode())
        if len(decoded) == 32:
            return key.encode()
    except Exception:
        pass
    
    # If not a valid Fernet key, derive a valid key using PBKDF2 from whatever string they provided
    # This guarantees deployment will never crash due to a format error with DATA_ENCRYPTION_KEY
    derived = hashlib.pbkdf2_hmac('sha256', key.encode(), b'mikrotik_dashboard_salt_91', 100000)
    return base64.urlsafe_b64encode(derived)

def encrypt_password(password: str) -> str:
    key = get_encryption_key()
    f = Fernet(key)
    return f.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password: str) -> str:
    key = get_encryption_key()
    f = Fernet(key)
    return f.decrypt(encrypted_password.encode()).decode()

def init_db():
    # Ensure database directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS routers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER NOT NULL,
            connection_type TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_routers():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, host, port, connection_type, username, created_at FROM routers ORDER BY created_at DESC")
    rows = cursor.fetchall()
    routers = []
    for row in rows:
        routers.append({
            "id": row["id"],
            "name": row["name"],
            "host": row["host"],
            "port": row["port"],
            "connection_type": row["connection_type"],
            "username": row["username"],
            "created_at": row["created_at"]
        })
    conn.close()
    return routers

def get_router_by_id(router_id: int):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM routers WHERE id = ?", (router_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            decrypted_pwd = decrypt_password(row["password"])
        except Exception:
            decrypted_pwd = "" # If encryption key changed, avoid absolute crash and return empty password
        return {
            "id": row["id"],
            "name": row["name"],
            "host": row["host"],
            "port": row["port"],
            "connection_type": row["connection_type"],
            "username": row["username"],
            "password": decrypted_pwd,
            "created_at": row["created_at"]
        }
    return None

def add_router(name: str, host: str, port: int, connection_type: str, username: str, password_raw: str) -> int:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    encrypted_pwd = encrypt_password(password_raw)
    created_at = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO routers (name, host, port, connection_type, username, password, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, host, port, connection_type, username, encrypted_pwd, created_at))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def delete_router(router_id: int) -> bool:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM routers WHERE id = ?", (router_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0
