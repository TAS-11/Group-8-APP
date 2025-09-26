import sqlite3 as _sqlite3
import datetime as _dt

DB_NAME = "schedule.db"


def init_db():
    conn = _sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            meeting_id INTEGER,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        )
        """
    )
    conn.commit()
    conn.close()


def add_meeting(title: str, channel_id: str) -> int:
    conn = _sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO meetings(title, channel_id, created_at) VALUES (?, ?, ?)",
        (title, channel_id, _dt.datetime.utcnow().isoformat()),
    )
    conn.commit()
    mid = cur.lastrowid
    conn.close()
    return mid


def add_option(meeting_id: int, text: str) -> int:
    conn = _sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO options(text, created_at, meeting_id) VALUES (?, ?, ?)",
        (text, _dt.datetime.utcnow().isoformat(), meeting_id),
    )
    conn.commit()
    oid = cur.lastrowid
    conn.close()
    return oid


def list_options(meeting_id: int):
    conn = _sqlite3.connect(DB_NAME)
    conn.row_factory = _sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM options WHERE meeting_id = ? ORDER BY id", (meeting_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
