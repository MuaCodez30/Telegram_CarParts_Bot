import sqlite3
from typing import List, Tuple, Optional
from datetime import datetime
import os

DB_PATH = "carparts.db"

def init_db():
    os.makedirs("images", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vin TEXT,
        oem TEXT,
        name TEXT,
        price REAL,
        description TEXT,
        photo_path TEXT,
        uploader_id INTEGER,
        uploader_username TEXT,
        upload_date TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_part(vin: str, oem: str, name: str, price: float, description: str,
             photo_path: str, uploader_id: int, uploader_username: Optional[str]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    upload_date = datetime.utcnow().isoformat()
    c.execute("""INSERT INTO parts
                 (vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date))
    conn.commit()
    conn.close()

def get_latest_parts(limit: int = 10) -> List[Tuple]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date FROM parts ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def search_parts_by_keyword(keyword: str) -> List[Tuple]:
    q = f"%{keyword.lower()}%"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT id, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date
                 FROM parts
                 WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ?""", (q, q))
    rows = c.fetchall()
    conn.close()
    return rows

def search_parts_by_vin(vin: str) -> List[Tuple]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT id, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date
                 FROM parts WHERE vin = ?""", (vin,))
    rows = c.fetchall()
    conn.close()
    return rows

def search_parts_by_oem(oem: str) -> List[Tuple]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT id, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date
                 FROM parts WHERE oem = ?""", (oem,))
    rows = c.fetchall()
    conn.close()
    return rows

def search_parts_by_price_range(min_p: float, max_p: float) -> List[Tuple]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT id, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date
                 FROM parts WHERE price BETWEEN ? AND ? ORDER BY price""", (min_p, max_p))
    rows = c.fetchall()
    conn.close()
    return rows

def get_part_by_id(part_id: int) -> Optional[Tuple]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT id, vin, oem, name, price, description, photo_path, uploader_id, uploader_username, upload_date
                 FROM parts WHERE id = ?""", (part_id,))
    row = c.fetchone()
    conn.close()
    return row

def fetch_parts(self, limit=5, offset=0):
    cursor = self.conn.cursor()
    cursor.execute(
        "SELECT * FROM parts ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

def count_parts(self):
    cursor = self.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM parts")
    return cursor.fetchone()[0]
