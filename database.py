import sqlite3
from pathlib import Path
from typing import Optional

from models import Incident
from seed_data import SEED_INCIDENTS

DB_PATH = Path(__file__).with_name("spotv_trouble.db")


def connect(db_path=DB_PATH):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path=DB_PATH):
    with connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_number TEXT NOT NULL UNIQUE,
            occurred_at TEXT NULL,
            equipment TEXT NOT NULL,
            symptom TEXT NOT NULL,
            cause TEXT NOT NULL,
            action TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            embedding TEXT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        if con.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 0:
            for item in SEED_INCIDENTS:
                _insert(con, item)
        con.execute("""CREATE TABLE IF NOT EXISTS manuals (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            drive_file_id TEXT NOT NULL DEFAULT '',
            drive_url TEXT NOT NULL DEFAULT '',
            file_hash TEXT NOT NULL,
            page_count INTEGER NOT NULL,
            extracted_pages INTEGER NOT NULL,
            chunk_count INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS manual_chunks (
            id TEXT PRIMARY KEY,
            manual_id TEXT NOT NULL,
            title TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            content TEXT NOT NULL,
            drive_url TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(manual_id) REFERENCES manuals(id) ON DELETE CASCADE
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_manual_chunks_manual ON manual_chunks(manual_id)")


def _insert(con, data, embedding=None):
    con.execute("""INSERT INTO incidents
        (incident_number, occurred_at, equipment, symptom, cause, action, notes, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (
        data["incident_number"].strip(), data.get("occurred_at") or None,
        data["equipment"].strip(), data["symptom"].strip(), data["cause"].strip(),
        data["action"].strip(), data.get("notes", "").strip(), embedding,
    ))


def list_incidents(db_path=DB_PATH):
    with connect(db_path) as con:
        return [Incident(**dict(row)) for row in con.execute("SELECT * FROM incidents ORDER BY incident_number")]


def add_incident(data, embedding=None, db_path=DB_PATH):
    with connect(db_path) as con:
        _insert(con, data, embedding)


def update_incident(incident_id: int, data, embedding=None, db_path=DB_PATH):
    with connect(db_path) as con:
        con.execute("""UPDATE incidents SET incident_number=?, occurred_at=?, equipment=?, symptom=?,
            cause=?, action=?, notes=?, embedding=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""", (
            data["incident_number"].strip(), data.get("occurred_at") or None,
            data["equipment"].strip(), data["symptom"].strip(), data["cause"].strip(),
            data["action"].strip(), data.get("notes", "").strip(), embedding, incident_id,
        ))


def delete_incident(incident_id: int, db_path=DB_PATH):
    with connect(db_path) as con:
        con.execute("DELETE FROM incidents WHERE id=?", (incident_id,))


def stats(db_path=DB_PATH):
    items = list_incidents(db_path)
    return len(items), len({i.equipment for i in items}), max((i.updated_at or "" for i in items), default="-")


def list_manuals(db_path=DB_PATH):
    with connect(db_path) as con:
        return [dict(row) for row in con.execute("SELECT * FROM manuals ORDER BY title")]


def list_manual_chunks(db_path=DB_PATH):
    with connect(db_path) as con:
        return [dict(row) for row in con.execute(
            "SELECT id, manual_id, title, page_number, content, drive_url FROM manual_chunks"
        )]


def replace_manual(metadata, chunks, db_path=DB_PATH):
    with connect(db_path) as con:
        con.execute("DELETE FROM manual_chunks WHERE manual_id=?", (metadata["id"],))
        con.execute("""INSERT INTO manuals
            (id,title,drive_file_id,drive_url,file_hash,page_count,extracted_pages,chunk_count,updated_at)
            VALUES (:id,:title,:drive_file_id,:drive_url,:file_hash,:page_count,:extracted_pages,:chunk_count,:updated_at)
            ON CONFLICT(id) DO UPDATE SET title=excluded.title, drive_file_id=excluded.drive_file_id,
            drive_url=excluded.drive_url, file_hash=excluded.file_hash, page_count=excluded.page_count,
            extracted_pages=excluded.extracted_pages, chunk_count=excluded.chunk_count,
            updated_at=excluded.updated_at""", metadata)
        con.executemany("""INSERT INTO manual_chunks
            (id,manual_id,title,page_number,content,drive_url)
            VALUES (:id,:manual_id,:title,:page_number,:content,:drive_url)""", chunks)


def delete_manual(manual_id, db_path=DB_PATH):
    with connect(db_path) as con:
        con.execute("DELETE FROM manual_chunks WHERE manual_id=?", (str(manual_id),))
        con.execute("DELETE FROM manuals WHERE id=?", (str(manual_id),))


def manual_stats(db_path=DB_PATH):
    manuals = list_manuals(db_path)
    return len(manuals), sum(item["page_count"] for item in manuals), sum(item["chunk_count"] for item in manuals)
