"""
Database setup for the mall parking system.
Uses SQLite for simplicity — swap the connection string for PostgreSQL later
by changing DATABASE_URL and installing psycopg2 (schema stays the same).
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "parking.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS vehicles (
        plate_number TEXT PRIMARY KEY,
        mobile_number TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS slots (
        slot_id TEXT PRIMARY KEY,
        gate_id TEXT,
        status TEXT DEFAULT 'free'   -- 'free' or 'occupied'
    );

    CREATE TABLE IF NOT EXISTS parking_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate_number TEXT,
        slot_id TEXT,
        gate_in TEXT,
        gate_out TEXT,
        entry_time TEXT,
        exit_time TEXT,
        status TEXT DEFAULT 'active'  -- 'active' or 'completed'
    );
    """)

    # Seed some parking slots if empty
    cur.execute("SELECT COUNT(*) FROM slots")
    if cur.fetchone()[0] == 0:
        slots = [(f"A{i}", "gate_1", "free") for i in range(1, 6)]
        cur.executemany("INSERT INTO slots (slot_id, gate_id, status) VALUES (?, ?, ?)", slots)

    # Seed one known vehicle for testing the "registered" path
    cur.execute("SELECT COUNT(*) FROM vehicles")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO vehicles (plate_number, mobile_number) VALUES (?, ?)",
            ("OD02AB1234", "+911234567890"),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
