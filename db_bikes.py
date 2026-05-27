"""SQLite database layer for Fahrradwerkstatt Worker (Gruppe 1)."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS kunden (
    kundenId INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    strasse TEXT,
    plz TEXT,
    ort TEXT,
    email TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS fahrraeder (
    objektId INTEGER PRIMARY KEY AUTOINCREMENT,
    kundenId INTEGER NOT NULL REFERENCES kunden(kundenId)
);

CREATE TABLE IF NOT EXISTS auftraege (
    auftragsId INTEGER PRIMARY KEY AUTOINCREMENT,
    kundenId INTEGER NOT NULL REFERENCES kunden(kundenId),
    objektId INTEGER NOT NULL REFERENCES fahrraeder(objektId),
    status TEXT NOT NULL DEFAULT 'offen'
        CHECK (status IN ('offen', 'in Bearbeitung', 'fertig'))
);
"""

ALLOWED_STATUS = ("offen", "in Bearbeitung", "fertig")

_db_path = None


def init(db_path: str):
    """Initialize database: create tables."""
    global _db_path
    _db_path = db_path
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_customer(kundenId: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM kunden WHERE kundenId = ?", (kundenId,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_bike(objektId: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM fahrraeder WHERE objektId = ?", (objektId,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_order(auftragsId: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM auftraege WHERE auftragsId = ?", (auftragsId,)).fetchone()
    conn.close()
    return dict(row) if row else None
