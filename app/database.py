import os
import sqlite3
import base64
from datetime import datetime
from cryptography.fernet import Fernet
import hashlib

DB_PATH = "/data/routers.db"

def get_encryption_key() -> bytes:
    key = os.getenv("DATA_ENCRYPTION_KEY", "default-mikrotik-dashboard-stable-secret-key")
    try:
        decoded = base64.urlsafe_b64decode(key.encode())
        if len(decoded) == 32:
            return key.encode()
    except Exception:
        pass
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
    cursor.execute("PRAGMA table_info(routers)")
    cols = [col[1] for col in cursor.fetchall()]
    if "snmp_community" not in cols:
        cursor.execute("ALTER TABLE routers ADD COLUMN snmp_community TEXT")
    if "snmp_port" not in cols:
        cursor.execute("ALTER TABLE routers ADD COLUMN snmp_port INTEGER")
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
    cursor.execute("SELECT id, name, host, port, connection_type, username, snmp_community, snmp_port, created_at FROM routers ORDER BY created_at DESC")
    rows = cursor.fetchall()
    routers = []
    for r in rows:
        routers.append({
            "id": r["id"], "name": r["name"], "host": r["host"], "port": r["port"],
            "connection_type": r["connection_type"], "username": r["username"],
            "snmp_community": r["snmp_community"] if r["snmp_community"] else "public",
            "snmp_port": r["snmp_port"] if r["snmp_port"] else 161,
            "created_at": r["created_at"]
        })
    conn.close()
    return routers

def get_router_by_id(router_id: int):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM routers WHERE id = ?", (router_id,))
    r = cursor.fetchone()
    conn.close()
    if r:
        try: decrypted_pwd = decrypt_password(r["password"])
        except Exception: decrypted_pwd = ""
        return {
            "id": r["id"], "name": r["name"], "host": r["host"], "port": r["port"],
            "connection_type": r["connection_type"], "username": r["username"],
            "password": decrypted_pwd,
            "snmp_community": r["snmp_community"] if r["snmp_community"] else "public",
            "snmp_port": r["snmp_port"] if r["snmp_port"] else 161,
            "created_at": r["created_at"]
        }
    return None

def add_router(name: str, host: str, port: int, connection_type: str, username: str, password_raw: str, snmp_community: str = "public", snmp_port: int = 161) -> int:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    encrypted_pwd = encrypt_password(password_raw)
    created_at = datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT INTO routers (name, host, port, connection_type, username, password, snmp_community, snmp_port, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, host, port, connection_type, username, encrypted_pwd, snmp_community, snmp_port, created_at))
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

