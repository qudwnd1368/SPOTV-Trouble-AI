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
